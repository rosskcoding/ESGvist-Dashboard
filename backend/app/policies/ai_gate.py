import json
import re
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.schemas.ai import AIResponse, SuggestedAction


class AIPermissionGate:
    ENDPOINT_PERMISSIONS: dict[str, list[str]] = {
        "explain_field": [
            "collector",
            "reviewer",
            "esg_manager",
            "auditor",
            "admin",
            "platform_admin",
        ],
        "explain_completeness": [
            "collector",
            "reviewer",
            "esg_manager",
            "auditor",
            "admin",
            "platform_admin",
        ],
        "explain_boundary": ["reviewer", "esg_manager", "admin", "platform_admin"],
        "explain_evidence": [
            "collector",
            "reviewer",
            "esg_manager",
            "auditor",
            "admin",
            "platform_admin",
        ],
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
        "access_token",
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
        if any(
            re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in self.INJECTION_PATTERNS
        ):
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

    # Route targets for navigate / open_dialog actions.
    ALLOWED_ROUTE_PREFIXES: set[str] = {
        "/dashboard",
        "/collection",
        "/evidence",
        "/validation",
        "/merge",
        "/completeness",
        "/report",
        "/requirements",
        "/settings/boundaries",
        "/settings/company-structure",
        "/settings/assignments",
        "/settings/standards",
        "/settings/shared-elements",
        "/boundary_view",
    }

    # DOM selector patterns for highlight actions.
    # Only data-ai-target attributes and #id selectors are allowed;
    # arbitrary CSS selectors (tag names, classes) are rejected so a
    # jailbroken LLM cannot probe the DOM.
    _HIGHLIGHT_PATTERN = re.compile(
        r"^(\[data-ai-target=[\"'][a-zA-Z0-9_:-]+[\"']\]|#[a-zA-Z][a-zA-Z0-9_-]*)$"
    )

    def _route_target_allowed(self, target: str) -> bool:
        if not target or not target.startswith("/"):
            return False
        return any(
            target == prefix or target.startswith(prefix + "/")
            for prefix in self.ALLOWED_ROUTE_PREFIXES
        )

    def _highlight_target_allowed(self, target: str) -> bool:
        if not target:
            return False
        return bool(self._HIGHLIGHT_PATTERN.match(target))

    def _target_allowed(self, action: SuggestedAction) -> bool:
        if action.action_type in ("navigate", "open_dialog"):
            return self._route_target_allowed(action.target)
        if action.action_type == "highlight":
            return self._highlight_target_allowed(action.target)
        return False

    def filter_actions(
        self, actions: list[SuggestedAction], ctx: RequestContext
    ) -> list[SuggestedAction]:
        allowed_types = self.ALLOWED_ACTIONS.get(ctx.role or "", set())
        return [
            action
            for action in actions
            if action.action_type in allowed_types and self._target_allowed(action)
        ]


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

    def validate(
        self, response: AIResponse, ctx: RequestContext
    ) -> tuple[AIResponse, bool, str | None]:
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
            response.text = (
                "Unable to verify a safe action. Please use the standard workflow controls."
            )
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
    # Abuse detection: max identical questions per hour before temp-block
    IDENTICAL_QUESTION_LIMIT = 10
    # Temp-ban duration after prompt injection attempt
    INJECTION_BAN_MINUTES = 60

    _minute_events: dict[int, deque[datetime]] = defaultdict(deque)
    _hour_events: dict[int, deque[datetime]] = defaultdict(deque)
    # Abuse tracking: user_id → deque of (timestamp, question_hash)
    _question_hashes: dict[int, deque[tuple[datetime, str]]] = defaultdict(deque)
    # Temp-ban: user_id → ban_until
    _banned_until: dict[int, datetime] = {}

    def check(self, ctx: RequestContext, *, question: str | None = None) -> None:
        now = datetime.now(UTC)
        limits = self.LIMITS.get(ctx.role or "", {"per_hour": 10, "per_minute": 2})

        # ── Temp-ban check ──────────────────────────────────────────
        ban_until = self._banned_until.get(ctx.user_id)
        if ban_until and now < ban_until:
            remaining = int((ban_until - now).total_seconds() // 60)
            raise AppError(
                "AI_TEMP_BANNED", 429,
                f"AI access temporarily suspended. Try again in {remaining} minute(s).",
            )

        # ── Per-minute burst ────────────────────────────────────────
        minute_cutoff = now - timedelta(minutes=1)
        minute_bucket = self._minute_events[ctx.user_id]
        while minute_bucket and minute_bucket[0] < minute_cutoff:
            minute_bucket.popleft()
        if len(minute_bucket) >= limits["per_minute"]:
            raise AppError(
                "AI_RATE_LIMITED", 429, "AI request limit exceeded. Try again in a minute."
            )

        # ── Per-hour ────────────────────────────────────────────────
        hour_cutoff = now - timedelta(hours=1)
        hour_bucket = self._hour_events[ctx.user_id]
        while hour_bucket and hour_bucket[0] < hour_cutoff:
            hour_bucket.popleft()
        if len(hour_bucket) >= limits["per_hour"]:
            raise AppError("AI_RATE_LIMITED", 429, "AI hourly limit exceeded.")

        # ── Identical question abuse ────────────────────────────────
        if question:
            q_hash = question.strip().lower()
            q_bucket = self._question_hashes[ctx.user_id]
            while q_bucket and q_bucket[0][0] < hour_cutoff:
                q_bucket.popleft()
            identical_count = sum(1 for _, h in q_bucket if h == q_hash)
            if identical_count >= self.IDENTICAL_QUESTION_LIMIT:
                raise AppError(
                    "AI_ABUSE_DETECTED", 429,
                    "Too many identical AI questions. Please vary your queries.",
                )
            q_bucket.append((now, q_hash))

        minute_bucket.append(now)
        hour_bucket.append(now)

    def ban_user(self, user_id: int) -> None:
        """Temporarily ban a user from AI (e.g. after prompt injection)."""
        self._banned_until[user_id] = datetime.now(UTC) + timedelta(
            minutes=self.INJECTION_BAN_MINUTES
        )
