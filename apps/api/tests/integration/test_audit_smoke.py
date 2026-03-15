"""
Minimal smoke tests for Audit Support API endpoints.

Tests that endpoints exist and return correct structure.
Uses existing fixtures (superuser client).

For full RBAC/tenant/role testing, see:
- FIXTURES_REQUIRED.md (explains what's needed)
- test_audit_rbac.py (RBAC scenarios with TODO)
- test_audit_tenant_isolation.py (tenant scenarios with TODO)
- test_audit_internal_visibility.py (visibility scenarios with TODO)
"""

import pytest
from httpx import AsyncClient
from uuid import UUID


@pytest.mark.asyncio
class TestEvidenceAPISmoke:
    """Smoke tests for Evidence API (superuser access)."""

    async def test_list_evidence_endpoint_exists(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
    ):
        """Evidence list endpoint returns paginated response."""
        # Get company_id from report
        report_resp = await auth_client.get(f"/api/v1/reports/{test_report_id}")
        assert report_resp.status_code == 200
        company_id = report_resp.json()["company_id"]

        # List evidence (should be empty)
        resp = await auth_client.get(f"/api/v1/companies/{company_id}/evidence")
        assert resp.status_code == 200
        data = resp.json()

        # Check paginated structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["items"], list)

    async def test_create_and_get_evidence(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """Create evidence and retrieve it."""
        # Get company_id
        report_resp = await auth_client.get(f"/api/v1/reports/{test_report_id}")
        company_id = report_resp.json()["company_id"]

        # Create evidence (type=note)
        create_resp = await auth_client.post(
            f"/api/v1/companies/{company_id}/evidence",
            json={
                "report_id": test_report_id,
                "scope_type": "section",
                "scope_id": test_section_id,
                "type": "note",
                "title": "Test Evidence",
                "note_md": "Test note content",
                "status": "provided",
            },
        )
        assert create_resp.status_code == 201
        evidence_id = create_resp.json()["evidence_id"]

        # Get evidence
        get_resp = await auth_client.get(
            f"/api/v1/companies/{company_id}/evidence/{evidence_id}"
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["title"] == "Test Evidence"
        assert data["status"] == "provided"
        assert data["type"] == "note"

    async def test_update_evidence_status(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """Update evidence status (workflow transition)."""
        # Get company_id
        report_resp = await auth_client.get(f"/api/v1/reports/{test_report_id}")
        company_id = report_resp.json()["company_id"]

        # Create evidence
        create_resp = await auth_client.post(
            f"/api/v1/companies/{company_id}/evidence",
            json={
                "report_id": test_report_id,
                "scope_type": "section",
                "scope_id": test_section_id,
                "type": "link",
                "title": "Test Link",
                "url": "https://example.com",
                "status": "provided",
            },
        )
        evidence_id = create_resp.json()["evidence_id"]

        # Update status: provided → reviewed
        update_resp = await auth_client.patch(
            f"/api/v1/companies/{company_id}/evidence/{evidence_id}",
            json={"status": "reviewed"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "reviewed"

    async def test_soft_delete_evidence(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """Soft delete evidence (sets deleted_at)."""
        # Get company_id
        report_resp = await auth_client.get(f"/api/v1/reports/{test_report_id}")
        company_id = report_resp.json()["company_id"]

        # Create evidence
        create_resp = await auth_client.post(
            f"/api/v1/companies/{company_id}/evidence",
            json={
                "report_id": test_report_id,
                "scope_type": "section",
                "scope_id": test_section_id,
                "type": "note",
                "title": "To Delete",
                "note_md": "Will be deleted",
            },
        )
        evidence_id = create_resp.json()["evidence_id"]

        # Delete (soft)
        delete_resp = await auth_client.delete(
            f"/api/v1/companies/{company_id}/evidence/{evidence_id}"
        )
        assert delete_resp.status_code == 204

        # Verify deleted_at is set (exclude by default)
        list_resp = await auth_client.get(f"/api/v1/companies/{company_id}/evidence")
        items = list_resp.json()["items"]
        assert not any(item["evidence_id"] == evidence_id for item in items)

        # Include deleted
        list_deleted_resp = await auth_client.get(
            f"/api/v1/companies/{company_id}/evidence?include_deleted=true"
        )
        items_with_deleted = list_deleted_resp.json()["items"]
        deleted_item = next((i for i in items_with_deleted if i["evidence_id"] == evidence_id), None)
        assert deleted_item is not None
        assert deleted_item["deleted_at"] is not None


@pytest.mark.asyncio
class TestCommentsAPISmoke:
    """Smoke tests for Comments API (superuser access)."""

    async def test_list_comment_threads_endpoint_exists(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
    ):
        """Comment threads list endpoint returns paginated response."""
        resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/comment-threads"
        )
        assert resp.status_code == 200
        data = resp.json()

        # Check paginated structure
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_create_thread_and_add_comment(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """Create comment thread and add comment."""
        # Create thread
        create_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "section",
                "anchor_id": test_section_id,
                "first_comment_body": "Test comment",
                "is_internal": False,
            },
        )
        assert create_resp.status_code == 201
        thread_id = create_resp.json()["thread_id"]

        # List threads filtered by the same anchor (this is what the UI uses)
        list_resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            params={"anchor_type": "section", "anchor_id": test_section_id},
        )
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert any(t["thread_id"] == thread_id for t in list_data["items"])

        # Get thread
        get_resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/comment-threads/{thread_id}"
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["status"] == "open"
        assert len(data["comments"]) == 1

    async def test_create_thread_for_block_anchor_and_list_filter(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_block_id: str,
    ):
        """Create comment thread anchored to a block and verify list filtering."""
        create_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "block",
                "anchor_id": test_block_id,
                "first_comment_body": "Block comment",
                "is_internal": False,
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        thread_id = create_resp.json()["thread_id"]

        list_resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            params={"anchor_type": "block", "anchor_id": test_block_id},
        )
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert any(t["thread_id"] == thread_id for t in list_data["items"])

    async def test_create_thread_is_idempotent_by_anchor(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """
        Creating a thread for the same anchor (same sub_anchor_type/sub_anchor_key)
        should append a comment to the existing thread instead of creating a new one.
        """
        first = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "section",
                "anchor_id": test_section_id,
                "first_comment_body": "First",
                "is_internal": False,
            },
        )
        assert first.status_code == 201, first.text
        thread_id = first.json()["thread_id"]

        second = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "section",
                "anchor_id": test_section_id,
                "first_comment_body": "Second",
                "is_internal": False,
            },
        )
        assert second.status_code == 201, second.text
        assert second.json()["thread_id"] == thread_id

        # Verify thread now has 2 comments
        get_resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/comment-threads/{thread_id}"
        )
        assert get_resp.status_code == 200
        assert len(get_resp.json()["comments"]) == 2

    async def test_create_thread_for_report_anchor(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
    ):
        """Report-level thread uses anchor_type='report' and anchor_id=report_id."""
        create_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "report",
                "anchor_id": test_report_id,
                "first_comment_body": "Report-level note",
                "is_internal": False,
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        thread_id = create_resp.json()["thread_id"]

        list_resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            params={"anchor_type": "report", "anchor_id": test_report_id},
        )
        assert list_resp.status_code == 200
        assert any(t["thread_id"] == thread_id for t in list_resp.json()["items"])

    async def test_resolve_and_reopen_thread(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """Resolve and reopen comment thread."""
        # Create thread
        create_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "section",
                "anchor_id": test_section_id,
                "first_comment_body": "Issue",
                "is_internal": False,
            },
        )
        thread_id = create_resp.json()["thread_id"]

        # Resolve
        resolve_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads/{thread_id}/resolve"
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["status"] == "resolved"
        assert resolve_resp.json()["resolved_at"] is not None

        # Reopen
        reopen_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads/{thread_id}/reopen"
        )
        assert reopen_resp.status_code == 200
        assert reopen_resp.json()["status"] == "open"
        assert reopen_resp.json()["resolved_at"] is None

    async def test_create_thread_with_wrong_anchor_type_returns_404(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
        test_section_id: str,
    ):
        """Verify that passing anchor_type='block' with section_id returns 404."""
        # Try to create thread with anchor_type='block' but anchor_id is actually a section_id
        create_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/comment-threads",
            json={
                "anchor_type": "block",  # Wrong type
                "anchor_id": test_section_id,  # This is actually a section_id
                "first_comment_body": "Test comment",
                "is_internal": False,
            },
        )
        # Should return 404 because block with this ID doesn't exist
        assert create_resp.status_code == 404
        assert "not found" in create_resp.json()["detail"].lower()


@pytest.mark.asyncio
class TestAuditPackAPISmoke:
    """Smoke tests for Audit Pack API (superuser access)."""

    async def test_create_audit_pack_job(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
    ):
        """Create audit pack generation job."""
        resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/audit-pack",
            json={
                "formats": ["evidences_csv", "comments_csv"],
                "locales": ["ru"],
                "include_internal_comments": False,
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # Check job structure
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["report_id"] == test_report_id

    async def test_get_audit_pack_job_status(
        self,
        auth_client: AsyncClient,
        test_report_id: str,
    ):
        """Get audit pack job status."""
        # Create job first
        create_resp = await auth_client.post(
            f"/api/v1/reports/{test_report_id}/audit-pack",
            json={"formats": ["evidences_csv"], "locales": ["ru"]},
        )
        job_id = create_resp.json()["job_id"]

        # Get status
        status_resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/audit-pack/{job_id}"
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["job_id"] == job_id
        assert "status" in data
        assert "artifacts" in data

