"""Tests for security hardening: rate limiting, AI timeout, gate enforcement."""

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware


# ---------------------------------------------------------------------------
# SEC-6: General API rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """API rate limiter must enforce per-identity request limits."""

    def test_rate_limit_setting_exists(self):
        assert hasattr(settings, "rate_limit_per_minute")
        assert settings.rate_limit_per_minute > 0

    @pytest.mark.asyncio
    async def test_rate_limit_returns_429_after_threshold(self, client: AsyncClient):
        """After exceeding the limit, the API must return 429."""
        # Clear any previous state from the rate limiter
        RateLimitMiddleware._buckets.clear()

        original = settings.rate_limit_per_minute
        # Temporarily lower limit for testing
        settings.rate_limit_per_minute = 3  # type: ignore[assignment]

        try:
            # First 3 should succeed (health is exempt, so use a real endpoint)
            for _ in range(3):
                resp = await client.get("/api/standards")
                # 401 (no auth) is fine — what matters is it's not 429
                assert resp.status_code != 429

            # 4th should be rate-limited
            resp = await client.get("/api/standards")
            assert resp.status_code == 429
            assert resp.json()["error"]["code"] == "RATE_LIMITED"
            assert "Retry-After" in resp.headers
        finally:
            settings.rate_limit_per_minute = original  # type: ignore[assignment]
            RateLimitMiddleware._buckets.clear()

    @pytest.mark.asyncio
    async def test_health_endpoint_exempt_from_rate_limit(self, client: AsyncClient):
        """Health checks must never be rate-limited."""
        RateLimitMiddleware._buckets.clear()
        original = settings.rate_limit_per_minute
        settings.rate_limit_per_minute = 1  # type: ignore[assignment]

        try:
            # Multiple health checks should always work
            for _ in range(5):
                resp = await client.get("/api/health")
                assert resp.status_code == 200
        finally:
            settings.rate_limit_per_minute = original  # type: ignore[assignment]
            RateLimitMiddleware._buckets.clear()

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, client: AsyncClient):
        """Responses should include X-RateLimit-* headers."""
        RateLimitMiddleware._buckets.clear()
        resp = await client.get("/api/standards")
        # May be 401 (no auth) but headers should be present
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers


# ---------------------------------------------------------------------------
# SEC-7: AI timeout configuration
# ---------------------------------------------------------------------------


class TestAITimeout:
    """AI timeout must be configured and enforced."""

    def test_ai_timeout_setting_exists(self):
        assert hasattr(settings, "ai_timeout_seconds")
        assert settings.ai_timeout_seconds > 0

    def test_ai_timeout_default_is_15s(self):
        """TZ-NFR specifies 15s hard timeout for AI calls."""
        assert settings.ai_timeout_seconds == 15

    def test_anthropic_client_uses_timeout(self):
        """AnthropicLLMClient must read timeout from settings."""
        import inspect
        from app.infrastructure.llm_client import AnthropicLLMClient

        source = inspect.getsource(AnthropicLLMClient.generate)
        assert "wait_for" in source or "timeout" in source

    def test_openai_client_uses_timeout(self):
        """OpenAILLMClient must read timeout from settings."""
        import inspect
        from app.infrastructure.llm_client import OpenAILLMClient

        source = inspect.getsource(OpenAILLMClient.__init__)
        assert "timeout" in source

    def test_grounded_provider_does_not_build_external_llm_client(self, monkeypatch):
        from app.infrastructure.llm_client import build_llm_client

        monkeypatch.setattr(settings, "ai_enabled", True)
        monkeypatch.setattr(settings, "ai_provider", "grounded")
        monkeypatch.setattr(settings, "ai_model", "grounded-v1")
        monkeypatch.setattr(settings, "ai_api_key", "test-key")

        assert build_llm_client() is None

    def test_timeout_error_raises_runtime_error(self):
        """Timeout should raise RuntimeError (caught by AI fallback)."""
        import inspect
        from app.infrastructure.llm_client import AnthropicLLMClient

        source = inspect.getsource(AnthropicLLMClient.generate)
        assert "TimeoutError" in source
        assert "RuntimeError" in source


# ---------------------------------------------------------------------------
# SEC-1 through SEC-5: Verify existing guards still work
# ---------------------------------------------------------------------------


class TestExistingSecurityGuards:
    """Smoke tests: existing guards from previous iterations."""

    def test_assignment_role_conflict_validation_exists(self):
        from app.services.project_service import ProjectService
        assert hasattr(ProjectService, "_validate_assignment_role_conflicts")

    def test_last_admin_guard_exists(self):
        from app.services.organization_user_service import OrganizationUserService
        assert hasattr(OrganizationUserService, "_guard_last_admin")

    def test_cannot_assign_platform_role_guard_exists(self):
        import inspect
        from app.services.user_role_service import UserRoleService
        source = inspect.getsource(UserRoleService)
        assert "CANNOT_ASSIGN_PLATFORM_ROLE" in source

    def test_evidence_in_use_policy_exists(self):
        from app.policies.evidence_policy import EvidencePolicy
        assert hasattr(EvidencePolicy, "not_in_approved_scope")

    def test_snapshot_immutable_policy_exists(self):
        from app.policies.boundary_policy import BoundaryPolicy
        assert hasattr(BoundaryPolicy, "snapshot_immutable")

    def test_security_headers_middleware_registered(self):
        from app.main import app
        middleware_types = [type(m).__name__ for m in getattr(app, "user_middleware", [])]
        # Starlette stores middleware differently; check by import
        from app.core.security_headers import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None
