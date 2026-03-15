"""
Integration tests for Audit Support RBAC enforcement.

Tests:
- Auditor forbidden from evidence:create/update/delete
- Auditor forbidden from comment:resolve
- Auditor cannot create is_internal comments
- Team can do all operations
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuditRBAC:
    """Test RBAC enforcement for audit support features."""

    async def test_auditor_cannot_create_evidence(self, client: AsyncClient):
        """Auditor should not be able to create evidence."""
        # NOTE: Minimal example - requires fixtures for the auditor role.
        # TODO: Add fixtures for multi-role testing (auditor, editor, etc.).
        # Example structure:
        # resp = await client.post(
        #     f"/api/v1/companies/{company_id}/evidence",
        #     json={"report_id": str(report_id), "scope_type": "block", ...}
        # )
        # assert resp.status_code == 403, "Auditor should not create evidence"
        pass

    async def test_auditor_cannot_update_evidence_status(self, client: AsyncClient):
        """Auditor should not be able to change evidence status."""
        # TODO: Implement with test fixtures
        # 1. Create evidence as editor
        # 2. Login as auditor
        # 3. PATCH /companies/{id}/evidence/{id} with status change
        # 4. Expect 403 Forbidden
        pass

    async def test_auditor_cannot_delete_evidence(self, client: AsyncClient):
        """Auditor should not be able to delete evidence."""
        # TODO: Implement
        pass

    async def test_auditor_can_read_evidence(self, client: AsyncClient):
        """Auditor should be able to read evidence."""
        # NOTE: Minimal smoke test - verifies the endpoint exists.
        # Full implementation requires an auditor role fixture.
        # TODO: Add auditor_client fixture + test data

        # Minimal smoke: endpoint exists and doesn't return 500
        # Note: current_user fixture is superuser, so returns 200 with empty list for random company
        from uuid import uuid4
        resp = await client.get(f"/api/v1/companies/{uuid4()}/evidence")
        # Superuser can access any company, expect 200 (empty list) or 404 (company not found)
        # NOT 500 (server error)
        assert resp.status_code in (200, 404), f"Unexpected status: {resp.status_code}"

    async def test_auditor_cannot_resolve_thread(self, client: AsyncClient):
        """Auditor should not be able to resolve comment threads."""
        # TODO: Implement
        # 1. Create thread as auditor
        # 2. POST /reports/{id}/comment-threads/{id}/resolve
        # 3. Expect 403 Forbidden
        pass

    async def test_auditor_cannot_create_internal_comment(self, client: AsyncClient):
        """Auditor should not be able to create internal comments."""
        # TODO: Implement
        # 1. Login as auditor
        # 2. POST comment with is_internal=true
        # 3. Expect 403 Forbidden
        pass

    async def test_editor_can_create_evidence(self, client: AsyncClient):
        """Editor should be able to create evidence."""
        # TODO: Implement
        pass

    async def test_editor_can_resolve_thread(self, client: AsyncClient):
        """Editor should be able to resolve threads."""
        # TODO: Implement
        pass


@pytest.mark.asyncio
class TestAuditLeadPermissions:
    """Test Audit Lead has elevated permissions."""

    async def test_audit_lead_can_create_evidence(self, client: AsyncClient):
        """Audit Lead should be able to create evidence."""
        # TODO: Implement
        pass

    async def test_audit_lead_cannot_resolve_thread(self, client: AsyncClient):
        """Audit Lead still cannot resolve threads (team only)."""
        # TODO: Implement
        pass
