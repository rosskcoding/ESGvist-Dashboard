import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.schemas.ai import AIResponse, SuggestedAction


class AIPermissionGate:
    ENDPOINT_PERMISSIONS: dict[str, list[str]] = {
        "explain_field": ["collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"],
        "explain_completeness": ["collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"],
        "explain_boundary": ["collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"],
        "review_assist": ["reviewer", "esg_manager", "admin", "platform_admin"],
        "ask": ["collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"],
    }

    def check(self, action: str, ctx: RequestContext) -> None:
        allowed_roles = self.ENDPOINT_PERMISSIONS.get(action, [])
        if ctx.role not in allowed_roles:
            raise AppError("FORBIDDEN", 403, f"AI {action} not available for role {ctx.role}")


class AIContextGate:
    SENSITIVE_KEYS = {
        "password_hash",
        "api_key",
        "refresh_token",
        "internal_notes",
        "raw_sql",
        "connection_string",
        "secret",
    }

    async def filter(self, raw_context: dict, ctx: RequestContext) -> dict:
        safe_context = dict(raw_context)
        org_id = safe_context.get("organization_id")
        if org_id is not None and ctx.organization_id is not None and org_id != ctx.organization_id:
            raise AppError("FORBIDDEN", 403, "AI context must stay within the active organization")

        for key in list(safe_context.keys()):
            if key in self.SENSITIVE_KEYS:
                safe_context.pop(key, None)

        if ctx.role == "collector":
            safe_context.pop("boundary_rules", None)
            safe_context.pop("assignment_matrix", None)
            safe_context.pop("other_users_data", None)
            safe_context["visibility"] = "collector_limited"
        elif ctx.role == "reviewer":
            safe_context.pop("assignment_matrix", None)
            safe_context["visibility"] = "reviewer_assigned_scope"
        elif ctx.role == "auditor":
            safe_context.pop("draft_comment", None)
            safe_context.pop("suggested_actions", None)
            safe_context["visibility"] = "auditor_read_only"

        serialized = json.dumps(safe_context, default=str)
        if len(serialized) > 8000:
            safe_context.pop("history", None)
            safe_context.pop("all_comments", None)
            safe_context["context_truncated"] = True

        return safe_context


class AIPromptGate:
    MAX_QUESTION_LENGTH = 500
    INJECTION_PATTERNS = [
        r"ignore previous instructions",
        r"you are now",
        r"system:",
        r"<\|im_start\|>",
        r"```system",
    ]

    def sanitize_question(self, question: str) -> str:
        clean_question = re.sub(r"<[^>]+>", "", question or "")
        clean_question = clean_question[: self.MAX_QUESTION_LENGTH]
        lowered = clean_question.lower()
        if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in self.INJECTION_PATTERNS):
            raise AppError("AI_PROMPT_INJECTION", 400, "Prompt injection attempt detected")
        return clean_question.strip()


class AIActionGate:
    ALLOWED_ACTIONS: dict[str, set[str]] = {
        "collector": {"navigate", "open_dialog", "highlight"},
        "reviewer": {"navigate", "highlight"},
        "esg_manager": {"navigate", "open_dialog", "highlight"},
        "admin": {"navigate", "open_dialog", "highlight"},
        "platform_admin": {"navigate", "open_dialog", "highlight"},
        "auditor": set(),
    }

    def filter_actions(self, actions: list[SuggestedAction], ctx: RequestContext) -> list[SuggestedAction]:
        allowed = self.ALLOWED_ACTIONS.get(ctx.role or "", set())
        return [action for action in actions if action.action_type in allowed]


class AIOutputGate:
    SENSITIVE_PATTERNS = [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        r"\b(password|secret|token|api_key)\s*[:=]\s*\S+",
        r"\b(SELECT|INSERT|UPDATE|DELETE)\s+.+FROM\b",
    ]
    FORBIDDEN_ACTION_TEXT = (
        "approve",
        "reject",
        "delete",
        "publish",
        "change the boundary",
    )

    def _strip_sensitive(self, value: str) -> tuple[str, bool]:
        cleaned = value
        changed = False
        for pattern in self.SENSITIVE_PATTERNS:
            new_value = re.sub(pattern, "[filtered]", cleaned, flags=re.IGNORECASE)
            if new_value != cleaned:
                changed = True
            cleaned = new_value
        return cleaned, changed

    def validate(self, response: AIResponse, ctx: RequestContext) -> tuple[AIResponse, bool, str | None]:
        if not response.text:
            return self.fallback("AI response was empty."), True, "empty_response"

        output_filtered = False
        filter_reasons: list[str] = []

        cleaned_text, changed = self._strip_sensitive(response.text)
        if changed:
            output_filtered = True
            filter_reasons.append("sensitive_text")
        response.text = cleaned_text

        if response.reasons:
            cleaned_reasons = []
            for reason in response.reasons:
                cleaned_reason, reason_changed = self._strip_sensitive(reason)
                if reason_changed:
                    output_filtered = True
                    filter_reasons.append("sensitive_reason")
                cleaned_reasons.append(cleaned_reason)
            response.reasons = cleaned_reasons

        if any(keyword in response.text.lower() for keyword in self.FORBIDDEN_ACTION_TEXT):
            output_filtered = True
            filter_reasons.append("forbidden_action_text")
            response.text = "Unable to verify a safe action. Please use the standard workflow controls."
            response.confidence = "low"

        if ctx.role == "auditor":
            if response.next_actions:
                output_filtered = True
                filter_reasons.append("auditor_read_only")
            response.next_actions = None

        reason = ",".join(dict.fromkeys(filter_reasons)) if filter_reasons else None
        return response, output_filtered, reason

    def fallback(self, reason: str) -> AIResponse:
        return AIResponse(
            text=f"AI temporarily unavailable. {reason}",
            reasons=["Static fallback was used"],
            confidence="low",
        )


class AIRateGate:
    LIMITS: dict[str, dict[str, int]] = {
        "collector": {"per_hour": 30, "per_minute": 5},
        "reviewer": {"per_hour": 50, "per_minute": 8},
        "esg_manager": {"per_hour": 100, "per_minute": 15},
        "admin": {"per_hour": 200, "per_minute": 20},
        "platform_admin": {"per_hour": 200, "per_minute": 20},
        "auditor": {"per_hour": 30, "per_minute": 5},
    }
    _minute_events: dict[int, deque[datetime]] = defaultdict(deque)
    _hour_events: dict[int, deque[datetime]] = defaultdict(deque)

    def check(self, ctx: RequestContext) -> None:
        now = datetime.now(timezone.utc)
        limits = self.LIMITS.get(ctx.role or "", {"per_hour": 10, "per_minute": 2})
        minute_cutoff = now - timedelta(minutes=1)
        hour_cutoff = now - timedelta(hours=1)

        minute_bucket = self._minute_events[ctx.user_id]
        while minute_bucket and minute_bucket[0] < minute_cutoff:
            minute_bucket.popleft()
        if len(minute_bucket) >= limits["per_minute"]:
            raise AppError("AI_RATE_LIMITED", 429, "AI request limit exceeded. Try again in a minute.")

        hour_bucket = self._hour_events[ctx.user_id]
        while hour_bucket and hour_bucket[0] < hour_cutoff:
            hour_bucket.popleft()
        if len(hour_bucket) >= limits["per_hour"]:
            raise AppError("AI_RATE_LIMITED", 429, "AI hourly limit exceeded.")

        minute_bucket.append(now)
        hour_bucket.append(now)
