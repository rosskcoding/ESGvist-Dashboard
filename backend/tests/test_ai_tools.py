"""Unit tests for AI tool access gate and tool definitions."""

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.schemas.ai import SuggestedAction
from app.services.ai_tools import (
    TOOL_REGISTRY,
    ToolAccessGate,
    get_scoped_completeness,
)
from tests.conftest import TestSessionLocal


def _ctx(role: str, user_id: int = 1) -> RequestContext:
    return RequestContext(
        user_id=user_id,
        email="test@test.com",
        organization_id=1,
        role=role,
    )


class TestToolAccessGate:
    gate = ToolAccessGate()

    def test_collector_can_access_requirement_details(self):
        self.gate.check_tool_allowed("get_requirement_details", _ctx("collector"))

    def test_collector_cannot_access_boundary_decision(self):
        with pytest.raises(AppError) as exc_info:
            self.gate.check_tool_allowed("get_boundary_decision", _ctx("collector"))
        assert exc_info.value.code == "AI_TOOL_FORBIDDEN"

    def test_collector_cannot_access_data_point_details(self):
        with pytest.raises(AppError) as exc_info:
            self.gate.check_tool_allowed("get_data_point_details", _ctx("collector"))
        assert exc_info.value.code == "AI_TOOL_FORBIDDEN"

    def test_collector_cannot_access_anomaly_flags(self):
        with pytest.raises(AppError) as exc_info:
            self.gate.check_tool_allowed("get_anomaly_flags", _ctx("collector"))
        assert exc_info.value.code == "AI_TOOL_FORBIDDEN"

    def test_collector_cannot_access_assignment_info(self):
        with pytest.raises(AppError) as exc_info:
            self.gate.check_tool_allowed("get_assignment_info", _ctx("collector"))
        assert exc_info.value.code == "AI_TOOL_FORBIDDEN"

    def test_collector_can_access_evidence_requirements(self):
        self.gate.check_tool_allowed("get_evidence_requirements", _ctx("collector"))

    def test_reviewer_can_access_data_point_details(self):
        self.gate.check_tool_allowed("get_data_point_details", _ctx("reviewer"))

    def test_reviewer_can_access_anomaly_flags(self):
        self.gate.check_tool_allowed("get_anomaly_flags", _ctx("reviewer"))

    def test_reviewer_can_access_boundary_decision(self):
        # Fix 5: reviewer must be able to call get_boundary_decision
        # so that explain_boundary endpoint doesn't 403
        self.gate.check_tool_allowed("get_boundary_decision", _ctx("reviewer"))

    def test_reviewer_cannot_access_assignment_info(self):
        with pytest.raises(AppError) as exc_info:
            self.gate.check_tool_allowed("get_assignment_info", _ctx("reviewer"))
        assert exc_info.value.code == "AI_TOOL_FORBIDDEN"

    def test_esg_manager_can_access_all_tools(self):
        for tool_name in TOOL_REGISTRY:
            self.gate.check_tool_allowed(tool_name, _ctx("esg_manager"))

    def test_admin_can_access_all_tools(self):
        for tool_name in TOOL_REGISTRY:
            self.gate.check_tool_allowed(tool_name, _ctx("admin"))

    def test_auditor_can_access_readonly_tools(self):
        self.gate.check_tool_allowed("get_requirement_details", _ctx("auditor"))
        self.gate.check_tool_allowed("get_standard_info", _ctx("auditor"))
        self.gate.check_tool_allowed("get_evidence_requirements", _ctx("auditor"))

    def test_auditor_cannot_access_write_adjacent_tools(self):
        with pytest.raises(AppError):
            self.gate.check_tool_allowed("get_boundary_decision", _ctx("auditor"))
        with pytest.raises(AppError):
            self.gate.check_tool_allowed("get_data_point_details", _ctx("auditor"))

    def test_unknown_tool_raises(self):
        with pytest.raises(AppError) as exc_info:
            self.gate.check_tool_allowed("nonexistent_tool", _ctx("admin"))
        assert exc_info.value.code == "AI_TOOL_NOT_FOUND"

    def test_get_tools_for_role_collector(self):
        tools = self.gate.get_tool_names_for_role("collector")
        assert "get_requirement_details" in tools
        assert "get_standard_info" in tools
        assert "get_evidence_requirements" in tools
        assert "get_boundary_decision" not in tools
        assert "get_data_point_details" not in tools

    def test_get_tools_for_role_esg_manager(self):
        tools = self.gate.get_tool_names_for_role("esg_manager")
        assert len(tools) == len(TOOL_REGISTRY)

    def test_get_blocked_tools_collector(self):
        blocked = self.gate.get_blocked_tools("collector")
        assert "get_boundary_decision" in blocked
        assert "get_data_point_details" in blocked
        assert "get_anomaly_flags" in blocked
        assert "get_assignment_info" in blocked
        assert "get_project_completeness" in blocked

    def test_get_blocked_tools_admin(self):
        blocked = self.gate.get_blocked_tools("admin")
        assert len(blocked) == 0


class TestToolRegistry:
    def test_all_tools_registered(self):
        expected = {
            "get_requirement_details",
            "get_standard_info",
            "get_boundary_decision",
            "get_project_completeness",
            "get_data_point_details",
            "get_evidence_requirements",
            "get_anomaly_flags",
            "get_assignment_info",
        }
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_tool_definitions_have_required_fields(self):
        for name, defn in TOOL_REGISTRY.items():
            assert defn.name == name
            assert defn.description
            assert defn.parameters
            assert len(defn.allowed_roles) > 0


class TestPermissionGateWithEvidence:
    """Verify that explain_boundary is now restricted from collectors."""

    def test_explain_boundary_not_available_for_collector(self):
        from app.policies.ai_gate import AIPermissionGate
        gate = AIPermissionGate()
        with pytest.raises(AppError) as exc_info:
            gate.check("explain_boundary", _ctx("collector"))
        assert exc_info.value.status_code == 403

    def test_explain_boundary_available_for_reviewer(self):
        """Fix 5: reviewer can access explain_boundary."""
        from app.policies.ai_gate import AIPermissionGate
        gate = AIPermissionGate()
        gate.check("explain_boundary", _ctx("reviewer"))

    def test_explain_evidence_available_for_collector(self):
        from app.policies.ai_gate import AIPermissionGate
        gate = AIPermissionGate()
        gate.check("explain_evidence", _ctx("collector"))

    def test_explain_evidence_available_for_auditor(self):
        from app.policies.ai_gate import AIPermissionGate
        gate = AIPermissionGate()
        gate.check("explain_evidence", _ctx("auditor"))


class TestReviewAssistOptionalEvidence:
    """Fix 4: optional evidence should NOT go into missing_evidence."""

    @pytest.mark.asyncio
    async def test_optional_evidence_not_in_missing_evidence(self):
        from app.services.ai_service import StaticAIProvider
        provider = StaticAIProvider("test")
        context = {
            "data_point_id": 1,
            "status": "in_review",
            "numeric_value": 42.0,
            "text_value": None,
            "shared_element_name": "Test Metric",
            "evidence_count": 0,
            "binding_count": 1,
            "requires_evidence": False,
        }
        result = await provider.review_assist(context)
        # missing_evidence should be EMPTY when evidence is optional
        assert len(result.missing_evidence) == 0
        # The info should be in anomalies instead
        assert any("optional" in a.lower() for a in result.anomalies)

    @pytest.mark.asyncio
    async def test_required_evidence_in_missing_evidence(self):
        from app.services.ai_service import StaticAIProvider
        provider = StaticAIProvider("test")
        context = {
            "data_point_id": 2,
            "status": "in_review",
            "numeric_value": 100.0,
            "text_value": None,
            "shared_element_name": "Required Metric",
            "evidence_count": 0,
            "binding_count": 1,
            "requires_evidence": True,
        }
        result = await provider.review_assist(context)
        # missing_evidence should contain the issue
        assert len(result.missing_evidence) > 0
        assert any("required" in m.lower() for m in result.missing_evidence)
        # draft_comment should be generated
        assert result.draft_comment is not None

    @pytest.mark.asyncio
    async def test_no_draft_comment_when_evidence_optional(self):
        from app.services.ai_service import StaticAIProvider
        provider = StaticAIProvider("test")
        context = {
            "data_point_id": 3,
            "status": "in_review",
            "numeric_value": 50.0,
            "text_value": None,
            "shared_element_name": "Optional Metric",
            "evidence_count": 0,
            "binding_count": 1,
            "requires_evidence": False,
        }
        result = await provider.review_assist(context)
        # No draft comment when evidence is optional
        assert result.draft_comment is None


class TestReviewerBoundaryAccess:
    """Fix 5: reviewer tool gate + permission gate must be consistent."""

    gate = ToolAccessGate()

    def test_reviewer_tool_and_permission_aligned(self):
        """Both gates allow reviewer to access boundary decision."""
        from app.policies.ai_gate import AIPermissionGate
        perm_gate = AIPermissionGate()

        # Permission gate allows
        perm_gate.check("explain_boundary", _ctx("reviewer"))
        # Tool gate also allows
        self.gate.check_tool_allowed("get_boundary_decision", _ctx("reviewer"))

    def test_collector_blocked_by_both_gates(self):
        """Collector is blocked by BOTH permission gate and tool gate."""
        from app.policies.ai_gate import AIPermissionGate
        perm_gate = AIPermissionGate()

        with pytest.raises(AppError):
            perm_gate.check("explain_boundary", _ctx("collector"))
        with pytest.raises(AppError):
            self.gate.check_tool_allowed("get_boundary_decision", _ctx("collector"))


class TestLLMBackedProvider:
    @pytest.mark.asyncio
    async def test_openai_provider_uses_llm_client(self, monkeypatch):
        from app.services.ai_service import LLMBackedAIProvider

        class _FakeLLMClient:
            model = "gpt-4o-mini"

            async def generate(self, system_prompt: str, user_message: str, *, tools=None) -> str:
                return (
                    '{"text":"Use the dashboard backlog and resolve the highest-priority blockers first.",'
                    '"reasons":["Generated by fake OpenAI client"],'
                    '"confidence":"high"}'
                )

            def parse_ai_response(self, raw: str):
                from app.schemas.ai import AIResponse

                return AIResponse(
                    text="Use the dashboard backlog and resolve the highest-priority blockers first.",
                    reasons=["Generated by fake OpenAI client"],
                    confidence="high",
                )

        monkeypatch.setattr(
            "app.infrastructure.llm_client.build_llm_client",
            lambda: _FakeLLMClient(),
        )

        provider = LLMBackedAIProvider("openai", "gpt-4o-mini")
        result = await provider.ask(
            "What should I check next?",
            {"screen": "dashboard", "project_name": "AI Project"},
        )

        assert result.provider == "openai"
        assert result.text.startswith("Use the dashboard backlog")
        assert "Generated by fake OpenAI client" in (result.reasons or [])

    @pytest.mark.asyncio
    async def test_ai_service_falls_back_when_llm_client_build_fails(self, monkeypatch):
        from app.services.ai_service import AIAssistantService

        monkeypatch.setattr(settings, "ai_enabled", True)
        monkeypatch.setattr(settings, "ai_provider", "openai")
        monkeypatch.setattr(settings, "ai_model", "gpt-4o")
        monkeypatch.setattr(settings, "ai_api_key", "test-key")
        monkeypatch.setattr(
            "app.infrastructure.llm_client.build_llm_client",
            lambda: (_ for _ in ()).throw(RuntimeError("openai package missing")),
        )

        service = AIAssistantService(session=None)
        response, model_name, used_fallback = await service._invoke_provider(
            "ask",
            "What should I check next?",
            {"screen": "dashboard"},
        )

        assert response.provider == "static"
        assert "Fallback provider was used" in (response.reasons or [])
        assert model_name == "static-fallback"
        assert used_fallback is True


class TestLLMResponseParsing:
    def _client(self):
        from app.infrastructure.llm_client import BaseLLMClient

        class _DummyClient(BaseLLMClient):
            async def generate(self, system_prompt: str, user_message: str, *, tools=None) -> str:
                return ""

            async def generate_stream(self, system_prompt: str, user_message: str, *, tools=None):
                if False:
                    yield ""

        return _DummyClient(model="dummy")

    def test_parse_ai_response_handles_code_fence_and_nested_shape(self):
        client = self._client()
        raw = """```json
{"AIResponse":{"message":"Check the dashboard backlog first.","confidence":"high"}}
```"""

        response = client.parse_ai_response(raw)

        assert response.text == "Check the dashboard backlog first."
        assert response.confidence == "high"

    def test_parse_ai_response_prefers_leading_text_over_embedded_json_block(self):
        client = self._client()
        raw = """You can manage entity hierarchy from this screen and review ownership links.

```json
{"AIResponse":{"tasks":["Manage hierarchy","Review ownership links"]}}
```"""

        response = client.parse_ai_response(raw)

        assert response.text == (
            "You can manage entity hierarchy from this screen and review ownership links."
        )
        assert "```json" not in response.text


class TestActionTargetAllowlist:
    """Backend must strip suggested actions whose target is not allowlisted."""

    def test_allowed_targets_pass(self):
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="Go", action_type="navigate", target="/dashboard"),
            SuggestedAction(label="Go", action_type="navigate", target="/collection"),
            SuggestedAction(label="Go", action_type="open_dialog", target="/evidence/upload"),
            SuggestedAction(label="Go", action_type="navigate", target="/completeness"),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 4

    def test_disallowed_targets_stripped(self):
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="Safe", action_type="navigate", target="/dashboard"),
            SuggestedAction(label="Evil", action_type="navigate", target="https://evil.com/steal"),
            SuggestedAction(label="Evil2", action_type="navigate", target="/etc/passwd"),
            SuggestedAction(label="Evil3", action_type="navigate", target="javascript:alert(1)"),
            SuggestedAction(label="Evil4", action_type="open_dialog", target="body"),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 1
        assert filtered[0].label == "Safe"

    def test_subpath_targets_allowed(self):
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="Go", action_type="navigate", target="/collection/123"),
            SuggestedAction(label="Go", action_type="navigate", target="/settings/boundaries/edit"),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 2

    def test_no_target_stripped(self):
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="Bad", action_type="navigate", target=""),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 0

    def test_highlight_with_data_ai_target_allowed(self):
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="HL", action_type="highlight", target='[data-ai-target="scope1-field"]'),
            SuggestedAction(label="HL", action_type="highlight", target="#evidence-section"),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 2

    def test_highlight_with_arbitrary_selector_blocked(self):
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="HL", action_type="highlight", target="body"),
            SuggestedAction(label="HL", action_type="highlight", target=".secret-class"),
            SuggestedAction(label="HL", action_type="highlight", target="div > span"),
            SuggestedAction(label="HL", action_type="highlight", target="*"),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 0

    def test_highlight_with_route_path_blocked(self):
        """highlight targets must be DOM selectors, not routes."""
        from app.policies.ai_gate import AIActionGate
        gate = AIActionGate()
        actions = [
            SuggestedAction(label="HL", action_type="highlight", target="/dashboard"),
        ]
        filtered = gate.filter_actions(actions, _ctx("admin"))
        assert len(filtered) == 0


class TestObjectLevelAccess:
    """Object-level access: collector/reviewer can only see own/assigned data points."""

    def test_check_data_point_access_exists(self):
        import inspect

        from app.services.ai_tools import _check_data_point_access
        assert inspect.iscoroutinefunction(_check_data_point_access)

    def test_get_data_point_details_calls_access_check(self):
        """get_data_point_details executor must include access check."""
        import inspect

        from app.services.ai_tools import _exec_get_data_point_details
        source = inspect.getsource(_exec_get_data_point_details)
        assert "_check_data_point_access" in source

    def test_get_anomaly_flags_calls_access_check(self):
        """get_anomaly_flags executor must include access check."""
        import inspect

        from app.services.ai_tools import _exec_get_anomaly_flags
        source = inspect.getsource(_exec_get_anomaly_flags)
        assert "_check_data_point_access" in source

    def test_admin_bypasses_check(self):
        """Admin should be in the bypass list."""
        import inspect

        from app.services.ai_tools import _check_data_point_access
        source = inspect.getsource(_check_data_point_access)
        assert '"admin"' in source or "'admin'" in source

    def test_collector_check_uses_assignments(self):
        """Collector access path must call get_user_assignments."""
        import inspect

        from app.services.ai_tools import _check_data_point_access
        source = inspect.getsource(_check_data_point_access)
        assert "get_user_assignments" in source
        assert "collector" in source

    def test_reviewer_check_uses_assignments(self):
        """Reviewer access path must call get_user_assignments."""
        import inspect

        from app.services.ai_tools import _check_data_point_access
        source = inspect.getsource(_check_data_point_access)
        assert "reviewer" in source

    def test_denied_error_code(self):
        """Denial should use AI_OBJECT_ACCESS_DENIED error code."""
        import inspect

        from app.services.ai_tools import _check_data_point_access
        source = inspect.getsource(_check_data_point_access)
        assert "AI_OBJECT_ACCESS_DENIED" in source


class TestScopedCompletenessSignature:
    """Fix 1 & 3: get_scoped_completeness must accept disclosure_id."""

    def test_function_accepts_disclosure_id_kwarg(self):
        import inspect

        from app.services.ai_tools import get_scoped_completeness
        sig = inspect.signature(get_scoped_completeness)
        assert "disclosure_id" in sig.parameters


async def _invite_and_accept(
    client: AsyncClient,
    admin_headers: dict,
    *,
    email: str,
    role: str,
    full_name: str,
) -> dict:
    invitation = await client.post(
        "/api/auth/invitations",
        json={"email": email, "role": role},
        headers=admin_headers,
    )
    assert invitation.status_code == 201

    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": full_name},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Organization-Id": admin_headers["X-Organization-Id"],
    }
    accept = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=headers,
    )
    assert accept.status_code == 200

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    return {"id": me.json()["id"], "headers": headers}


@pytest.mark.asyncio
async def test_scoped_completeness_limits_missing_items_to_assignment_disclosures(
    client: AsyncClient,
):
    await client.post(
        "/api/auth/register",
        json={"email": "ai-scope-admin@test.com", "password": "password123", "full_name": "AI Scope Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "ai-scope-admin@test.com", "password": "password123"},
    )
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post(
        "/api/organizations/setup",
        json={"name": "AI Scope Org", "country": "GB"},
        headers=admin_headers,
    )
    assert org.status_code == 201
    admin_headers["X-Organization-Id"] = str(org.json()["organization_id"])

    collector = await _invite_and_accept(
        client,
        admin_headers,
        email="ai-scope-collector@test.com",
        role="collector",
        full_name="AI Scope Collector",
    )

    standard = await client.post(
        "/api/standards",
        json={"code": "AI_SCOPE_STD", "name": "AI Scope Standard"},
        headers=admin_headers,
    )
    assert standard.status_code == 201

    disclosure_a = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "DISC-A",
            "title": "Disclosure A",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    disclosure_b = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "DISC-B",
            "title": "Disclosure B",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    assert disclosure_a.status_code == 201
    assert disclosure_b.status_code == 201

    item_a = await client.post(
        f"/api/disclosures/{disclosure_a.json()['id']}/items",
        json={"name": "Assigned Item", "item_type": "metric", "value_type": "number", "is_required": True},
        headers=admin_headers,
    )
    item_a_missing = await client.post(
        f"/api/disclosures/{disclosure_a.json()['id']}/items",
        json={"name": "Sibling Missing Item", "item_type": "metric", "value_type": "number", "is_required": True},
        headers=admin_headers,
    )
    item_b = await client.post(
        f"/api/disclosures/{disclosure_b.json()['id']}/items",
        json={"name": "Foreign Disclosure Item", "item_type": "metric", "value_type": "number", "is_required": True},
        headers=admin_headers,
    )
    assert item_a.status_code == 201
    assert item_a_missing.status_code == 201
    assert item_b.status_code == 201

    element_a = await client.post(
        "/api/shared-elements",
        json={"code": "AI_SCOPE_A", "name": "AI Scope Element A"},
        headers=admin_headers,
    )
    element_b = await client.post(
        "/api/shared-elements",
        json={"code": "AI_SCOPE_B", "name": "AI Scope Element B"},
        headers=admin_headers,
    )
    assert element_a.status_code == 201
    assert element_b.status_code == 201

    mapping_a = await client.post(
        "/api/mappings",
        json={"requirement_item_id": item_a.json()["id"], "shared_element_id": element_a.json()["id"]},
        headers=admin_headers,
    )
    mapping_b = await client.post(
        "/api/mappings",
        json={"requirement_item_id": item_b.json()["id"], "shared_element_id": element_b.json()["id"]},
        headers=admin_headers,
    )
    assert mapping_a.status_code == 201
    assert mapping_b.status_code == 201

    project = await client.post(
        "/api/projects",
        json={"name": "AI Scope Project"},
        headers=admin_headers,
    )
    assert project.status_code == 201
    add_standard = await client.post(
        f"/api/projects/{project.json()['id']}/standards",
        json={"standard_id": standard.json()["id"], "is_base_standard": True},
        headers=admin_headers,
    )
    assert add_standard.status_code == 200

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": element_a.json()["id"],
            "collector_id": collector["id"],
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 201

    for item_id in (
        item_a.json()["id"],
        item_a_missing.json()["id"],
        item_b.json()["id"],
    ):
        status_resp = await client.get(
            f"/api/projects/{project.json()['id']}/completeness/items/{item_id}",
            headers=admin_headers,
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "missing"

    collector_me = await client.get("/api/auth/me", headers=collector["headers"])
    assert collector_me.status_code == 200
    collector_ctx = RequestContext(
        user_id=collector_me.json()["id"],
        email=collector_me.json()["email"],
        organization_id=org.json()["organization_id"],
        role="collector",
    )

    async with TestSessionLocal() as session:
        scoped = await get_scoped_completeness(
            session,
            project.json()["id"],
            collector_ctx,
        )

    assert set(scoped["missing_items"]) == {
        "Assigned Item",
        "Sibling Missing Item",
    }
    assert "Foreign Disclosure Item" not in scoped["missing_items"]
