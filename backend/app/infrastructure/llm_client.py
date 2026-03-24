"""LLM client abstraction with provider adapters and tool-loop support.

Supports:
- Anthropic (Claude) via anthropic SDK
- OpenAI-compatible APIs via openai SDK
- Static fallback (no network, deterministic)

The client exposes two methods:
- explain(): structured context -> AIResponse
- ask(): question + context + tools -> AIResponse (with tool loop)

Both return parsed AIResponse / ReviewAssistResponse.
Streaming is handled separately via stream_ask() which yields NDJSON chunks.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from app.core.config import settings
from app.schemas.ai import AIResponse, Reference, ReviewAssistResponse, SuggestedAction
from app.services.ai_tools import TOOL_REGISTRY, ToolDefinition

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS: dict[str, str] = {
    "field_explanation": (
        "You are an ESG reporting assistant. Explain the given requirement field "
        "to the user in clear language. Use the provided context. "
        "Do not invent data. Respond in structured JSON matching the AIResponse schema: "
        '{"text": "...", "reasons": [...], "references": [...], "confidence": "high|medium|low"}.'
    ),
    "completeness_explanation": (
        "You are an ESG reporting assistant. Explain why the project is at the "
        "given completeness level. List missing/partial items and suggest next steps. "
        "Respond in structured JSON matching the AIResponse schema."
    ),
    "boundary_explanation": (
        "You are an ESG reporting assistant. Explain the boundary inclusion/exclusion "
        "decision for the given entity. Cite the inclusion source and consolidation method. "
        "Respond in structured JSON matching the AIResponse schema."
    ),
    "evidence_explanation": (
        "You are an ESG reporting assistant. Explain the evidence requirements "
        "for the given requirement item. Indicate what types of evidence are expected "
        "and whether the current evidence is sufficient. "
        "Respond in structured JSON matching the AIResponse schema."
    ),
    "contextual_qa": (
        "You are an ESG reporting assistant embedded in a dashboard. "
        "Answer the user's question using ONLY the provided context and tools. "
        "Never fabricate data. If you cannot answer, say so. "
        "Respond in structured JSON matching the AIResponse schema."
    ),
    "review_assist": (
        "You are an ESG reporting assistant helping a reviewer. "
        "Summarize the data point, flag anomalies, note missing evidence, "
        "and draft a review comment if needed. "
        "Respond in structured JSON matching the ReviewAssistResponse schema: "
        '{"summary": "...", "anomalies": [...], "missing_evidence": [...], '
        '"draft_comment": "...|null", "reuse_impact": "...|null"}.'
    ),
}


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseLLMClient(ABC):
    """Abstract base for LLM provider clients."""

    def __init__(self, model: str, max_tokens: int = 1024, temperature: float = 0.2):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        tools: list[dict] | None = None,
    ) -> str:
        """Generate a completion. Returns raw text response."""

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """Generate a streaming completion. Yields text chunks."""

    def parse_ai_response(self, raw: str) -> AIResponse:
        """Parse LLM output into AIResponse."""
        try:
            data = json.loads(raw)
            return AIResponse(
                text=data.get("text", raw),
                reasons=data.get("reasons"),
                next_actions=[
                    SuggestedAction(**a) for a in (data.get("next_actions") or [])
                ] or None,
                references=[
                    Reference(**r) for r in (data.get("references") or [])
                ] or None,
                confidence=data.get("confidence", "medium"),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            return AIResponse(text=raw, confidence="low")

    def parse_review_response(self, raw: str) -> ReviewAssistResponse:
        """Parse LLM output into ReviewAssistResponse."""
        try:
            data = json.loads(raw)
            return ReviewAssistResponse(
                summary=data.get("summary", raw),
                anomalies=data.get("anomalies", []),
                missing_evidence=data.get("missing_evidence", []),
                draft_comment=data.get("draft_comment"),
                reuse_impact=data.get("reuse_impact"),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            return ReviewAssistResponse(
                summary=raw, anomalies=[], missing_evidence=[]
            )


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------

class AnthropicLLMClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ):
        super().__init__(model, max_tokens, temperature)
        self._timeout = settings.ai_timeout_seconds
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            raise RuntimeError(
                "anthropic package is required for Anthropic provider. "
                "Install it with: pip install anthropic"
            )

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        tools: list[dict] | None = None,
    ) -> str:
        try:
            response = await asyncio.wait_for(
                self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"AI request timed out after {self._timeout}s"
            )
        return response.content[0].text if response.content else ""

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


# ---------------------------------------------------------------------------
# OpenAI-compatible adapter
# ---------------------------------------------------------------------------

class OpenAILLMClient(BaseLLMClient):
    """Client for OpenAI-compatible APIs (OpenAI, Azure, local models)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ):
        super().__init__(model, max_tokens, temperature)
        self._timeout = settings.ai_timeout_seconds
        try:
            from openai import AsyncOpenAI
            kwargs: dict[str, Any] = {"api_key": api_key, "timeout": self._timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = AsyncOpenAI(**kwargs)
        except ImportError:
            raise RuntimeError(
                "openai package is required for OpenAI provider. "
                "Install it with: pip install openai"
            )

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        tools: list[dict] | None = None,
    ) -> str:
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"AI request timed out after {self._timeout}s"
            )
        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_llm_client() -> BaseLLMClient | None:
    """Build an LLM client from settings. Returns None if AI is disabled
    or no API key is configured."""
    if not settings.ai_enabled or not settings.ai_api_key:
        return None

    provider = (settings.ai_provider or "static").lower()
    model = settings.ai_model or "static-ai"
    max_tokens = settings.ai_max_tokens
    temperature = settings.ai_temperature

    if provider in ("anthropic", "claude", "grounded"):
        return AnthropicLLMClient(
            api_key=settings.ai_api_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    if provider in ("openai", "azure", "gpt"):
        return OpenAILLMClient(
            api_key=settings.ai_api_key,
            model=model,
            base_url=settings.ai_base_url or None,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    return None


def get_system_prompt(prompt_type: str) -> str:
    return SYSTEM_PROMPTS.get(prompt_type, SYSTEM_PROMPTS["contextual_qa"])


def format_context_for_llm(context: dict) -> str:
    """Serialize context dict into a human-readable string for the LLM."""
    parts = []
    for key, value in context.items():
        if value is None or key in ("organization_id", "visibility"):
            continue
        if isinstance(value, dict):
            parts.append(f"{key}: {json.dumps(value, default=str, indent=2)}")
        elif isinstance(value, list):
            items = ", ".join(str(v) for v in value[:10])
            suffix = f" (and {len(value) - 10} more)" if len(value) > 10 else ""
            parts.append(f"{key}: [{items}{suffix}]")
        else:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def tool_definitions_for_llm(tools: list[ToolDefinition]) -> list[dict]:
    """Convert internal tool definitions to LLM function-calling format."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": {
                "type": "object",
                "properties": {
                    k: {"type": v.get("type", "string")}
                    for k, v in t.parameters.items()
                    if not v.get("optional")
                },
                "required": [
                    k for k, v in t.parameters.items() if not v.get("optional")
                ],
            },
        }
        for t in tools
    ]
