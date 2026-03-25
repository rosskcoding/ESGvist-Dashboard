"""AI Assistant orchestration service.

Responsibilities:
- Gate checks (permission, rate, prompt, context, output, action, tool access)
- Context building via ai_tools (scoped to user's assignments)
- Provider dispatch with automatic fallback
- Audit logging with tools_used / tools_blocked
"""

import json
from time import perf_counter

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_data_point_for_ctx, get_project_for_ctx
from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.metrics import record_non_blocking_failure
from app.db.models.ai_interaction import AIInteraction
from app.db.models.completeness import RequirementItemDataPoint
from app.db.models.requirement_item import RequirementItem
from app.policies.ai_gate import (
    AIActionGate,
    AIContextGate,
    AIOutputGate,
    AIPermissionGate,
    AIPromptGate,
    AIRateGate,
)
from app.schemas.ai import (
    AIResponse,
    AIStatusOut,
    AskRequest,
    ExplainEvidenceRequest,
    ExplainRequest,
    Reference,
    ReviewAssistResponse,
    SuggestedAction,
)
from app.services.ai_tools import (
    ToolAccessGate,
    execute_tool,
    get_scoped_completeness,
)

logger = structlog.get_logger("app.ai")


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class BaseAIProvider:
    provider_name = "base"
    capabilities = [
        "explain_field",
        "explain_completeness",
        "explain_boundary",
        "explain_evidence",
        "ask",
        "review_assist",
    ]

    def __init__(self, model_name: str):
        self.model_name = model_name


class StaticAIProvider(BaseAIProvider):
    provider_name = "static"

    def __init__(self, model_name: str):
        super().__init__(model_name)

    async def explain_field(self, context: dict) -> AIResponse:
        item = context.get("requirement_item", {})
        requires_evidence = item.get("requires_evidence")
        reasons = [
            f"Field type: {item.get('item_type', 'unknown')}",
            f"Expected value type: {item.get('value_type', 'unknown')}",
        ]
        if requires_evidence:
            reasons.append("Supporting evidence is required for this item")
        return AIResponse(
            text=(
                f"'{item.get('name', 'This field')}' captures a required ESG disclosure input for the "
                f"current reporting workflow."
            ),
            reasons=reasons,
            references=[
                Reference(
                    title=item.get("name", "Requirement item"),
                    source="Requirement Item Registry",
                )
            ],
            confidence="high",
            provider=self.provider_name,
        )

    async def explain_completeness(self, context: dict) -> AIResponse:
        status_counts = context.get("status_counts", {})
        reasons = []
        if status_counts.get("missing"):
            reasons.append(f"{status_counts['missing']} requirement items are still missing")
        if status_counts.get("partial"):
            reasons.append(f"{status_counts['partial']} requirement items are only partially complete")
        if context.get("scope_note"):
            reasons.append(f"Scope: {context['scope_note']}")
        if not reasons:
            reasons.append("No completeness blockers were detected in the visible scope")
        return AIResponse(
            text=(
                f"Project completeness is {context.get('completion_percent', 0)}% "
                f"for the visible scope."
            ),
            reasons=reasons,
            next_actions=[
                SuggestedAction(
                    label="Open collection workspace",
                    action_type="navigate",
                    target="/collection",
                    description="Review missing or partial data points",
                )
            ],
            confidence="high" if context.get("completion_percent", 0) >= 80 else "medium",
            provider=self.provider_name,
        )

    async def explain_boundary(self, context: dict) -> AIResponse:
        inclusion = context.get("inclusion_status")
        if inclusion is None:
            text = "Boundary explanation requires a project and entity context."
            reasons = ["No boundary decision could be verified from the provided context"]
        elif inclusion:
            text = "This entity is included in the active project boundary."
            reasons = [context.get("boundary_reason", "A matching boundary membership includes this entity.")]
        else:
            text = "This entity is excluded from the active project boundary."
            reasons = [context.get("boundary_reason", "No active inclusion rule was found for this entity.")]
        return AIResponse(
            text=text,
            reasons=reasons,
            confidence="high" if inclusion is not None else "low",
            provider=self.provider_name,
        )

    async def explain_evidence(self, context: dict) -> AIResponse:
        item = context.get("requirement_item", {})
        requires_evidence = item.get("requires_evidence", False)
        evidence_gap = context.get("evidence_gap", 0)
        evidence_sufficient = context.get("evidence_sufficient", True)

        reasons = []
        if requires_evidence:
            reasons.append("This requirement item mandates supporting evidence")
        else:
            reasons.append("Evidence is optional for this item but recommended for audit readiness")

        if evidence_gap > 0:
            reasons.append(
                f"{evidence_gap} data point(s) are missing linked evidence"
            )
        elif requires_evidence:
            reasons.append("All bound data points have linked evidence")

        text_parts = [
            f"Evidence status for '{item.get('name', 'this item')}':",
        ]
        if requires_evidence:
            text_parts.append(
                "Sufficient" if evidence_sufficient else "Insufficient"
            )
        else:
            text_parts.append("Optional (not required by the standard)")

        next_actions = []
        if not evidence_sufficient:
            next_actions.append(
                SuggestedAction(
                    label="Upload evidence",
                    action_type="open_dialog",
                    target="/evidence/upload",
                    description="Attach supporting evidence to the data point",
                )
            )

        return AIResponse(
            text=" ".join(text_parts),
            reasons=reasons,
            next_actions=next_actions or None,
            references=[
                Reference(
                    title=item.get("name", "Requirement item"),
                    source=item.get("standard_code", "Requirement Item Registry"),
                )
            ],
            confidence="high" if evidence_sufficient else "medium",
            provider=self.provider_name,
        )

    async def ask(self, question: str, context: dict) -> AIResponse:
        screen = context.get("screen") or "current workspace"
        actions = [
            SuggestedAction(
                label="Open current workspace",
                action_type="navigate",
                target=f"/{screen}" if not str(screen).startswith("/") else str(screen),
                description="Stay in the current UI flow while resolving the issue",
            )
        ]
        references = []
        if context.get("project_name"):
            references.append(Reference(title=context["project_name"], source="Reporting Project"))
        return AIResponse(
            text=f"AI guidance is based on the '{screen}' screen context. Question received: {question}",
            reasons=["Response was generated from filtered backend context", "No write action was executed"],
            next_actions=actions,
            references=references or None,
            confidence="medium",
            provider=self.provider_name,
        )

    async def review_assist(self, context: dict) -> ReviewAssistResponse:
        missing_evidence = []
        requires_evidence = context.get("requires_evidence", True)
        if context.get("evidence_count", 0) == 0 and requires_evidence:
            missing_evidence.append("No evidence linked (evidence is required)")

        anomalies = []
        if context.get("evidence_count", 0) == 0 and not requires_evidence:
            anomalies.append("No evidence linked (optional, but recommended for audit readiness)")
        if context.get("status") != "in_review":
            anomalies.append(f"Status is '{context.get('status')}', not 'in_review'")
        if context.get("numeric_value") is None and not context.get("text_value"):
            anomalies.append("Data point has no reported value")

        draft_comment = None
        if context.get("status") == "in_review" and missing_evidence and requires_evidence:
            draft_comment = "Please attach supporting evidence before approval."

        summary = (
            f"Data point #{context['data_point_id']} records "
            f"{context.get('shared_element_name', 'an ESG metric')}."
        )
        if context.get("numeric_value") is not None:
            summary += f" Current numeric value: {context['numeric_value']}."

        return ReviewAssistResponse(
            summary=summary,
            anomalies=anomalies,
            missing_evidence=missing_evidence,
            draft_comment=draft_comment,
            reuse_impact=f"Reused in {context.get('binding_count', 0)} requirement item(s).",
            provider=self.provider_name,
        )


class GroundedAIProvider(StaticAIProvider):
    provider_name = "grounded"

    async def explain_field(self, context: dict) -> AIResponse:
        item = context.get("requirement_item", {})
        reasons = []
        if item.get("description"):
            reasons.append(item["description"])
        if item.get("is_required"):
            reasons.append("This field is marked as required in the active disclosure")
        if item.get("requires_evidence"):
            reasons.append("Approved values for this field require supporting evidence")
        if item.get("standard_code"):
            reasons.append(f"Grounded in {item['standard_code']} / {item.get('disclosure_code', 'disclosure')}")
        if not reasons:
            reasons = ["Field guidance was generated from the available requirement metadata"]
        return AIResponse(
            text=(
                f"{item.get('name', 'This field')} expects a "
                f"{item.get('value_type', 'structured')} value for the current ESG disclosure."
            ),
            reasons=reasons[:4],
            references=[
                Reference(
                    title=item.get("name", "Requirement item"),
                    source=item.get("standard_code", "Requirement Item Registry"),
                )
            ],
            next_actions=[
                SuggestedAction(
                    label="Open field details",
                    action_type="open_dialog",
                    target="/requirements",
                    description="Review the requirement definition before entering data",
                )
            ],
            confidence="high",
            provider=self.provider_name,
        )

    async def explain_completeness(self, context: dict) -> AIResponse:
        missing_items = context.get("missing_items", [])
        partial_items = context.get("partial_items", [])
        reasons = []
        if missing_items:
            reasons.append(f"Missing items: {', '.join(missing_items[:3])}")
        if partial_items:
            reasons.append(f"Partial items: {', '.join(partial_items[:3])}")
        if context.get("scope_note"):
            reasons.append(f"Visible scope: {context['scope_note']}")
        if not reasons:
            reasons.append("No completeness blockers were detected in the grounded project state")
        return AIResponse(
            text=(
                f"Project '{context.get('project_name', 'project')}' is {context.get('completion_percent', 0)}% complete."
            ),
            reasons=reasons,
            next_actions=[
                SuggestedAction(
                    label="Review blockers",
                    action_type="navigate",
                    target="/dashboard",
                    description="Open the dashboard and resolve missing or partial requirements",
                )
            ],
            references=[
                Reference(title=context.get("project_name", "Project"), source="Reporting Project")
            ],
            confidence="high" if not missing_items and not partial_items else "medium",
            provider=self.provider_name,
        )

    async def ask(self, question: str, context: dict) -> AIResponse:
        lowered = question.lower()
        reasons = ["Answer grounded in backend context and current screen state"]
        references = []
        if context.get("project_name"):
            references.append(Reference(title=context["project_name"], source="Reporting Project"))
        if "boundary" in lowered and context.get("project_name"):
            text = f"Boundary questions should be resolved in the context of project '{context['project_name']}'."
            if context.get("project_status"):
                reasons.append(f"Current project status: {context['project_status']}")
        elif "complete" in lowered or "missing" in lowered:
            text = (
                f"Use the completeness workspace for '{context.get('project_name', 'the project')}' "
                "to inspect missing and partial items."
            )
            if context.get("project_status"):
                reasons.append(f"Project status: {context['project_status']}")
        else:
            text = f"AI guidance is grounded in the '{context.get('screen') or 'current'}' workspace context."
        return AIResponse(
            text=text,
            reasons=reasons,
            next_actions=[
                SuggestedAction(
                    label="Open current workspace",
                    action_type="navigate",
                    target=f"/{context.get('screen')}" if context.get("screen") else "/dashboard",
                    description="Continue from the active workflow context",
                )
            ],
            references=references or None,
            confidence="medium",
            provider=self.provider_name,
        )

    async def review_assist(self, context: dict) -> ReviewAssistResponse:
        anomalies = list(context.get("anomaly_flags", []))
        if context.get("value_delta_percent") is not None:
            anomalies.append(f"Value delta vs peer baseline: {context['value_delta_percent']}%")
        response = await super().review_assist(context)
        response.anomalies = sorted(set(response.anomalies + anomalies))
        response.provider = self.provider_name
        return response


class UnavailableAIProvider(BaseAIProvider):
    provider_name = "unavailable"

    async def explain_field(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def explain_completeness(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def explain_boundary(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def explain_evidence(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def ask(self, question: str, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def review_assist(self, context: dict) -> ReviewAssistResponse:
        raise RuntimeError("Primary AI provider unavailable")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AIAssistantService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_gate = AIPermissionGate()
        self.context_gate = AIContextGate()
        self.prompt_gate = AIPromptGate()
        self.action_gate = AIActionGate()
        self.output_gate = AIOutputGate()
        self.rate_gate = AIRateGate()
        self.tool_gate = ToolAccessGate()
        self.configured_provider = getattr(settings, "ai_provider", "static")
        model_name = settings.ai_model if hasattr(settings, "ai_model") else "static-ai"
        self.primary_provider = self._build_provider(self.configured_provider, model_name)
        self.fallback_provider = StaticAIProvider(model_name="static-fallback")

    @staticmethod
    def _classify_ai_exception(exc: Exception, *, prefix: str) -> tuple[str, str]:
        if isinstance(exc, AppError):
            return f"{prefix}_app_error", getattr(exc, "code", "APP_ERROR")

        exception_type = type(exc).__name__
        lowered = exception_type.lower()
        if isinstance(exc, TimeoutError) or "timeout" in lowered:
            return f"{prefix}_timeout", exception_type
        if isinstance(exc, ConnectionError) or any(
            marker in lowered for marker in ("network", "connect", "connection")
        ):
            return f"{prefix}_transport_error", exception_type
        return f"{prefix}_unexpected_error", exception_type

    @staticmethod
    def _build_provider(provider_name: str, model_name: str) -> BaseAIProvider:
        normalized = (provider_name or "static").lower()
        if not getattr(settings, "ai_enabled", False):
            return StaticAIProvider(model_name="static-ai")
        if normalized == "grounded":
            return GroundedAIProvider(model_name=model_name)
        if normalized == "unavailable":
            return UnavailableAIProvider(model_name=model_name)
        return StaticAIProvider(model_name=model_name)

    async def _invoke_provider(self, method_name: str, *args):
        provider = self.primary_provider
        try:
            result = await getattr(provider, method_name)(*args)
            return result, provider.model_name, False
        except Exception as exc:
            if provider.model_name == self.fallback_provider.model_name:
                raise
            fallback_result = await getattr(self.fallback_provider, method_name)(*args)
            if isinstance(fallback_result, AIResponse):
                fallback_result.provider = self.fallback_provider.provider_name
                fallback_result.reasons = list(fallback_result.reasons or []) + ["Fallback provider was used"]
            elif isinstance(fallback_result, ReviewAssistResponse):
                fallback_result.provider = self.fallback_provider.provider_name
                fallback_result.anomalies = list(fallback_result.anomalies or []) + ["Fallback provider was used"]
            failure_operation, failure_reason = self._classify_ai_exception(
                exc,
                prefix="provider",
            )
            try:
                record_non_blocking_failure("ai_service", failure_operation)
                logger.warning(
                    "ai_provider_call_failed",
                    method_name=method_name,
                    provider=provider.provider_name,
                    model=provider.model_name,
                    failure_reason=failure_reason,
                    exception_type=type(exc).__name__,
                    exc_info=True,
                )
            except Exception:
                pass
            return fallback_result, self.fallback_provider.model_name, True

    def get_status(self) -> AIStatusOut:
        return AIStatusOut(
            enabled=getattr(settings, "ai_enabled", False),
            configured_provider=self.configured_provider,
            effective_provider=self.primary_provider.provider_name,
            model=self.primary_provider.model_name,
            fallback_model=self.fallback_provider.model_name,
            capabilities=list(self.primary_provider.capabilities),
        )

    async def _log(
        self,
        *,
        ctx: RequestContext,
        action: str,
        screen: str | None,
        question: str | None,
        safe_context: dict | None,
        response_summary: str | None,
        latency_ms: int,
        gate_blocked: bool = False,
        gate_reason: str | None = None,
        tools_blocked: list[str] | None = None,
        tools_used: list[str] | None = None,
        output_filtered: bool = False,
        output_filter_reason: str | None = None,
        model_name: str | None = None,
    ) -> None:
        interaction = AIInteraction(
            user_id=ctx.user_id,
            organization_id=ctx.organization_id,
            role=ctx.role or "unknown",
            screen=screen,
            action=action,
            context_summary=json.dumps(safe_context or {}, default=str)[:500],
            question=question[:500] if question else None,
            response_summary=response_summary[:500] if response_summary else None,
            model=model_name or self.primary_provider.model_name,
            latency_ms=latency_ms,
            gate_blocked=gate_blocked,
            gate_reason=gate_reason,
            tools_blocked=",".join(tools_blocked or []) if tools_blocked else None,
            tools_used=",".join(tools_used or []) if tools_used else None,
            output_filtered=output_filtered,
            output_filter_reason=output_filter_reason,
        )
        self.session.add(interaction)
        await self.session.flush()
        await self.session.commit()

    async def _run_ai_action(
        self,
        *,
        action: str,
        ctx: RequestContext,
        screen: str | None,
        question: str | None,
        raw_context_builder,
        response_builder,
        tools_used: list[str] | None = None,
    ):
        started = perf_counter()
        safe_context: dict | None = None
        clean_question = None
        try:
            self.rate_gate.check(ctx, question=question)
            self.permission_gate.check(action, ctx)
            raw_context = await raw_context_builder()
            safe_context = await self.context_gate.filter(raw_context, ctx)
            if question is not None:
                try:
                    clean_question = self.prompt_gate.sanitize_question(question)
                except AppError as injection_exc:
                    if injection_exc.code == "AI_PROMPT_INJECTION":
                        self.rate_gate.ban_user(ctx.user_id)
                    raise
            provider_response = await response_builder(safe_context, clean_question)
            if isinstance(provider_response, tuple):
                response, model_name, used_fallback = provider_response
            else:
                response = provider_response
                model_name = self.primary_provider.model_name
                used_fallback = False
            if isinstance(response, AIResponse):
                response, output_filtered, filter_reason = self.output_gate.validate(response, ctx)
                if response.next_actions:
                    original_count = len(response.next_actions)
                    response.next_actions = self.action_gate.filter_actions(response.next_actions, ctx)
                    if len(response.next_actions) != original_count:
                        output_filtered = True
                        filter_reason = ",".join(
                            value for value in [filter_reason, "action_gate"] if value
                        )
                if used_fallback:
                    output_filtered = True
                    filter_reason = ",".join(value for value in [filter_reason, "provider_fallback"] if value)
                await self._log(
                    ctx=ctx,
                    action=action,
                    screen=screen,
                    question=clean_question,
                    safe_context=safe_context,
                    response_summary=response.text,
                    latency_ms=int((perf_counter() - started) * 1000),
                    tools_blocked=self.tool_gate.get_blocked_tools(ctx.role or ""),
                    tools_used=tools_used,
                    output_filtered=output_filtered,
                    output_filter_reason=filter_reason,
                    model_name=model_name,
                )
            else:
                await self._log(
                    ctx=ctx,
                    action=action,
                    screen=screen,
                    question=clean_question,
                    safe_context=safe_context,
                    response_summary=response.summary,
                    latency_ms=int((perf_counter() - started) * 1000),
                    tools_blocked=self.tool_gate.get_blocked_tools(ctx.role or ""),
                    tools_used=tools_used,
                    model_name=model_name,
                )
            return response
        except Exception as exc:
            if hasattr(exc, "code"):
                await self._log(
                    ctx=ctx,
                    action=action,
                    screen=screen,
                    question=clean_question or question,
                    safe_context=safe_context,
                    response_summary=None,
                    latency_ms=int((perf_counter() - started) * 1000),
                    gate_blocked=True,
                    gate_reason=getattr(exc, "code", None),
                    tools_blocked=self.tool_gate.get_blocked_tools(ctx.role or ""),
                    tools_used=tools_used,
                )
                raise

            failure_operation, failure_reason = self._classify_ai_exception(
                exc,
                prefix="action",
            )
            try:
                record_non_blocking_failure("ai_service", failure_operation)
                logger.warning(
                    "ai_action_fallback_served",
                    action=action,
                    screen=screen,
                    user_id=ctx.user_id,
                    organization_id=ctx.organization_id,
                    failure_reason=failure_reason,
                    exception_type=type(exc).__name__,
                    exc_info=True,
                )
            except Exception:
                pass
            fallback = self.output_gate.fallback("AI backend failed to produce a verified response.")
            await self._log(
                ctx=ctx,
                action=action,
                screen=screen,
                question=clean_question or question,
                safe_context=safe_context,
                response_summary=fallback.text,
                latency_ms=int((perf_counter() - started) * 1000),
                gate_blocked=True,
                gate_reason="AI_UNAVAILABLE",
                tools_blocked=self.tool_gate.get_blocked_tools(ctx.role or ""),
                tools_used=tools_used,
                output_filtered=True,
                output_filter_reason="fallback",
            )
            return fallback

    # -- explain_field -------------------------------------------------------

    async def explain_field(self, payload: ExplainRequest, ctx: RequestContext) -> AIResponse:
        from app.core.ai_cache import FIELD_EXPLAIN_TTL, ai_cache

        # Cache hit check (field explanations are stable, TTL 24h)
        cache_key = payload.requirement_item_id
        if cache_key:
            cached = ai_cache.get("field_explain", cache_key)
            if cached is not None:
                return cached

        tools_used = []

        async def raw_context_builder() -> dict:
            if payload.requirement_item_id:
                self.tool_gate.check_tool_allowed("get_requirement_details", ctx)
                tool_result = await execute_tool(
                    "get_requirement_details",
                    {"requirement_item_id": payload.requirement_item_id},
                    self.session,
                    ctx,
                )
                tools_used.append("get_requirement_details")
                return {
                    "organization_id": ctx.organization_id,
                    "requirement_item": tool_result,
                }
            return {
                "organization_id": ctx.organization_id,
                "requirement_item": {"name": "Field"},
            }

        result = await self._run_ai_action(
            action="explain_field",
            ctx=ctx,
            screen="field_explain",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_field", safe_context
            ),
            tools_used=tools_used,
        )

        # Cache the result
        if cache_key and isinstance(result, AIResponse):
            ai_cache.set("field_explain", cache_key, result, FIELD_EXPLAIN_TTL)

        return result

    # -- explain_completeness ------------------------------------------------

    async def explain_completeness(self, payload: ExplainRequest, ctx: RequestContext) -> AIResponse:
        tools_used = []

        async def raw_context_builder() -> dict:
            project = await get_project_for_ctx(self.session, payload.project_id or 0, ctx)
            tools_used.append("get_project_completeness")
            scoped = await get_scoped_completeness(
                self.session, project.id, ctx,
                disclosure_id=payload.disclosure_id,
            )
            scoped["project_name"] = project.name
            scoped["organization_id"] = project.organization_id
            return scoped

        return await self._run_ai_action(
            action="explain_completeness",
            ctx=ctx,
            screen="completeness",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_completeness", safe_context
            ),
            tools_used=tools_used,
        )

    # -- explain_boundary ----------------------------------------------------

    async def explain_boundary(self, payload: ExplainRequest, ctx: RequestContext) -> AIResponse:
        tools_used = []

        async def raw_context_builder() -> dict:
            raw_context: dict = {
                "organization_id": ctx.organization_id,
                "entity_id": payload.entity_id,
            }
            if payload.project_id:
                project = await get_project_for_ctx(self.session, payload.project_id, ctx)
                raw_context["project_id"] = project.id
                raw_context["project_name"] = project.name
                raw_context["organization_id"] = project.organization_id
                if payload.entity_id and project.boundary_definition_id:
                    self.tool_gate.check_tool_allowed("get_boundary_decision", ctx)
                    tool_result = await execute_tool(
                        "get_boundary_decision",
                        {
                            "entity_id": payload.entity_id,
                            "boundary_id": project.boundary_definition_id,
                        },
                        self.session,
                        ctx,
                    )
                    tools_used.append("get_boundary_decision")
                    raw_context["inclusion_status"] = tool_result.get("included", False)
                    raw_context["boundary_reason"] = (
                        f"Inclusion source: {tool_result.get('inclusion_source')}"
                        if tool_result.get("included")
                        else tool_result.get("reason", "No boundary membership includes this entity")
                    )
                    if tool_result.get("consolidation_method"):
                        raw_context["consolidation_method"] = tool_result["consolidation_method"]
            return raw_context

        return await self._run_ai_action(
            action="explain_boundary",
            ctx=ctx,
            screen="boundary",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_boundary", safe_context
            ),
            tools_used=tools_used,
        )

    # -- explain_evidence ----------------------------------------------------

    async def explain_evidence(
        self, payload: ExplainEvidenceRequest, ctx: RequestContext
    ) -> AIResponse:
        tools_used = []

        async def raw_context_builder() -> dict:
            self.tool_gate.check_tool_allowed("get_evidence_requirements", ctx)
            tool_result = await execute_tool(
                "get_evidence_requirements",
                {"requirement_item_id": payload.requirement_item_id},
                self.session,
                ctx,
            )
            tools_used.append("get_evidence_requirements")

            # Also fetch requirement details for richer context
            self.tool_gate.check_tool_allowed("get_requirement_details", ctx)
            item_details = await execute_tool(
                "get_requirement_details",
                {"requirement_item_id": payload.requirement_item_id},
                self.session,
                ctx,
            )
            tools_used.append("get_requirement_details")

            return {
                "organization_id": ctx.organization_id,
                "requirement_item": item_details,
                "requires_evidence": tool_result.get("requires_evidence", False),
                "evidence_gap": tool_result.get("evidence_gap", 0),
                "evidence_sufficient": tool_result.get("evidence_sufficient", True),
                "total_bound_data_points": tool_result.get("total_bound_data_points", 0),
                "data_points_with_evidence": tool_result.get("data_points_with_evidence", 0),
            }

        return await self._run_ai_action(
            action="explain_evidence",
            ctx=ctx,
            screen="evidence",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_evidence", safe_context
            ),
            tools_used=tools_used,
        )

    # -- ask -----------------------------------------------------------------

    async def ask(self, payload: AskRequest, ctx: RequestContext) -> AIResponse:
        tools_used = []

        async def raw_context_builder() -> dict:
            raw_context = dict(payload.context or {})
            raw_context["organization_id"] = ctx.organization_id
            raw_context["screen"] = payload.screen
            if payload.context and payload.context.get("project_id"):
                project = await get_project_for_ctx(self.session, payload.context["project_id"], ctx)
                raw_context["project_name"] = project.name
                raw_context["project_status"] = project.status
            return raw_context

        return await self._run_ai_action(
            action="ask",
            ctx=ctx,
            screen=payload.screen,
            question=payload.question,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, clean_question: self._invoke_provider(
                "ask",
                clean_question or "",
                safe_context,
            ),
            tools_used=tools_used,
        )

    # -- ask_stream ----------------------------------------------------------

    async def ask_stream_prepare(
        self, payload: AskRequest, ctx: RequestContext
    ) -> dict:
        """Run all gates and build context **before** the HTTP response starts.

        Returns a prepared context dict that ask_stream_generate() consumes.
        Any gate violation raises an AppError here — the route handler sees
        it as a normal exception and returns a proper HTTP 400/403/429
        (not a 200 with an NDJSON error event).

        Also logs blocked requests so they appear in the audit trail.
        """
        started = perf_counter()
        clean_question: str | None = None
        safe_context: dict | None = None

        try:
            self.rate_gate.check(ctx, question=payload.question)
            self.permission_gate.check("ask", ctx)

            raw_context = dict(payload.context or {})
            raw_context["organization_id"] = ctx.organization_id
            raw_context["screen"] = payload.screen
            if payload.context and payload.context.get("project_id"):
                project = await get_project_for_ctx(
                    self.session, payload.context["project_id"], ctx
                )
                raw_context["project_name"] = project.name
                raw_context["project_status"] = project.status

            safe_context = await self.context_gate.filter(raw_context, ctx)
            try:
                clean_question = self.prompt_gate.sanitize_question(payload.question)
            except AppError as injection_exc:
                if injection_exc.code == "AI_PROMPT_INJECTION":
                    self.rate_gate.ban_user(ctx.user_id)
                raise
        except Exception as exc:
            if not hasattr(exc, "code"):
                failure_operation, failure_reason = self._classify_ai_exception(
                    exc,
                    prefix="prepare",
                )
                try:
                    record_non_blocking_failure("ai_service", failure_operation)
                    logger.error(
                        "ai_stream_prepare_failed",
                        screen=payload.screen,
                        user_id=ctx.user_id,
                        organization_id=ctx.organization_id,
                        failure_reason=failure_reason,
                        exception_type=type(exc).__name__,
                        exc_info=True,
                    )
                except Exception:
                    pass
            # Log the blocked request for audit
            await self._log(
                ctx=ctx,
                action="ask_stream",
                screen=payload.screen,
                question=clean_question or payload.question,
                safe_context=safe_context,
                response_summary=None,
                latency_ms=int((perf_counter() - started) * 1000),
                gate_blocked=True,
                gate_reason=getattr(exc, "code", "UNKNOWN"),
            )
            raise

        return {
            "safe_context": safe_context,
            "clean_question": clean_question,
            "started": started,
        }

    async def ask_stream_generate(
        self, prepared: dict, payload: AskRequest, ctx: RequestContext
    ):
        """Async generator that yields (event_type, data) tuples.

        Called only after ask_stream_prepare() succeeds, so gates have
        already passed and context is built.
        """
        from app.infrastructure.llm_client import (
            build_llm_client,
            format_context_for_llm,
            get_system_prompt,
        )

        safe_context = prepared["safe_context"]
        clean_question = prepared["clean_question"]
        started = prepared["started"]
        output_filtered = False
        filter_reason: str | None = None
        model_name = self.primary_provider.model_name
        used_fallback = False

        # ── Try real LLM streaming ───────────────────────────────────
        llm_client = build_llm_client()
        if llm_client is not None:
            system_prompt = get_system_prompt("contextual_qa")
            user_message = (
                f"Context:\n{format_context_for_llm(safe_context)}\n\n"
                f"Question: {clean_question}"
            )
            accumulated: list[str] = []
            try:
                async for chunk in llm_client.generate_stream(
                    system_prompt, user_message
                ):
                    accumulated.append(chunk)
                    yield ("chunk", chunk)

                full_text = "".join(accumulated)
                response = llm_client.parse_ai_response(full_text)
                response.provider = self.primary_provider.provider_name
                model_name = llm_client.model
            except Exception as exc:
                # Primary LLM failed mid-stream → fall back
                failure_operation, failure_reason = self._classify_ai_exception(
                    exc,
                    prefix="stream",
                )
                try:
                    record_non_blocking_failure("ai_service", failure_operation)
                    logger.warning(
                        "ai_stream_provider_failed",
                        screen=payload.screen,
                        user_id=ctx.user_id,
                        organization_id=ctx.organization_id,
                        model=getattr(llm_client, "model", None),
                        failure_reason=failure_reason,
                        exception_type=type(exc).__name__,
                        exc_info=True,
                    )
                except Exception:
                    pass
                used_fallback = True
                response, model_name, _ = await self._invoke_provider(
                    "ask", clean_question, safe_context
                )
                words = (response.text or "").split(" ")
                for i, word in enumerate(words):
                    yield ("chunk", word if i == 0 else " " + word)
        else:
            # No LLM client → provider chain with fallback
            response, model_name, used_fallback = await self._invoke_provider(
                "ask", clean_question, safe_context
            )
            words = (response.text or "").split(" ")
            for i, word in enumerate(words):
                yield ("chunk", word if i == 0 else " " + word)

        # ── Output / action gates ────────────────────────────────────
        if isinstance(response, AIResponse):
            response, output_filtered, filter_reason = self.output_gate.validate(response, ctx)
            if response.next_actions:
                original_count = len(response.next_actions)
                response.next_actions = self.action_gate.filter_actions(
                    response.next_actions, ctx
                )
                if len(response.next_actions) != original_count:
                    output_filtered = True
                    filter_reason = ",".join(
                        v for v in [filter_reason, "action_gate"] if v
                    )
            if used_fallback:
                output_filtered = True
                filter_reason = ",".join(
                    v for v in [filter_reason, "provider_fallback"] if v
                )

        yield ("done", response)

        # ── Audit log ────────────────────────────────────────────────
        await self._log(
            ctx=ctx,
            action="ask_stream",
            screen=payload.screen,
            question=clean_question,
            safe_context=safe_context,
            response_summary=(response.text if isinstance(response, AIResponse) else str(response))[:500],
            latency_ms=int((perf_counter() - started) * 1000),
            tools_blocked=self.tool_gate.get_blocked_tools(ctx.role or ""),
            output_filtered=output_filtered,
            output_filter_reason=filter_reason,
            model_name=model_name,
        )

    # -- review_assist -------------------------------------------------------

    async def review_assist(self, data_point_id: int, ctx: RequestContext) -> ReviewAssistResponse | AIResponse:
        tools_used = []

        async def raw_context_builder() -> dict:
            data_point, project, _ = await get_data_point_for_ctx(self.session, data_point_id, ctx)

            # Use tools for data gathering
            self.tool_gate.check_tool_allowed("get_data_point_details", ctx)
            dp_details = await execute_tool(
                "get_data_point_details",
                {"data_point_id": data_point_id},
                self.session,
                ctx,
            )
            tools_used.append("get_data_point_details")

            self.tool_gate.check_tool_allowed("get_anomaly_flags", ctx)
            anomaly_result = await execute_tool(
                "get_anomaly_flags",
                {"data_point_id": data_point_id},
                self.session,
                ctx,
            )
            tools_used.append("get_anomaly_flags")

            # Check if evidence is required via bound requirement items
            bound_items = (
                await self.session.execute(
                    select(RequirementItem.requires_evidence)
                    .join(
                        RequirementItemDataPoint,
                        RequirementItemDataPoint.requirement_item_id == RequirementItem.id,
                    )
                    .where(RequirementItemDataPoint.data_point_id == data_point.id)
                )
            ).scalars().all()
            requires_evidence = any(bound_items)

            return {
                "organization_id": project.organization_id,
                "project_id": project.id,
                "data_point_id": data_point.id,
                "status": data_point.status,
                "numeric_value": dp_details.get("numeric_value"),
                "text_value": dp_details.get("text_value"),
                "shared_element_name": dp_details.get("shared_element_name"),
                "evidence_count": dp_details.get("evidence_count", 0),
                "binding_count": dp_details.get("binding_count", 0),
                "anomaly_flags": anomaly_result.get("anomalies", []),
                "value_delta_percent": anomaly_result.get("value_delta_percent"),
                "requires_evidence": requires_evidence,
            }

        return await self._run_ai_action(
            action="review_assist",
            ctx=ctx,
            screen="review_assist",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "review_assist", safe_context
            ),
            tools_used=tools_used,
        )
