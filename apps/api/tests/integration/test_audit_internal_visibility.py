"""
Integration tests for is_internal comment visibility.

Tests:
- Auditors don't see is_internal=true comments
- Team members see all comments
- Audit pack export respects include_internal_comments flag
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestInternalCommentVisibility:
    """Test is_internal comment visibility filtering."""

    async def test_auditor_cannot_see_internal_comments(self, client: AsyncClient):
        """Auditor should not see is_internal=true comments."""
        # NOTE: Minimal smoke test - checks the comment threads endpoint.
        # Full implementation requires thread fixtures + auditor role.
        # TODO: Add create_thread_with_comments fixture + auditor_client

        # Minimal smoke: endpoint exists
        from uuid import uuid4
        report_id = uuid4()
        resp = await client.get(f"/api/v1/reports/{report_id}/comment-threads")
        # Expect 404 (report not found) or 200, not 500
        assert resp.status_code in (200, 404), f"Unexpected status: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data, "Missing 'items' in response"

    async def test_editor_sees_all_comments(self, client: AsyncClient):
        """Editor should see all comments including internal."""
        # TODO: Implement
        # 1. Create thread with internal + public comments
        # 2. Login as editor
        # 3. GET thread
        # 4. Expect both comments visible
        pass

    async def test_audit_pack_excludes_internal_by_default(self, client: AsyncClient):
        """Audit pack should exclude internal comments by default."""
        # TODO: Implement
        # 1. Create comments (some internal)
        # 2. Generate audit pack with include_internal_comments=false
        # 3. Download comments.csv
        # 4. Verify internal comments not in CSV
        pass

    async def test_audit_pack_includes_internal_when_requested(self, client: AsyncClient):
        """Audit pack can include internal comments if requested."""
        # TODO: Implement
        # 1. Create comments (some internal)
        # 2. Generate audit pack with include_internal_comments=true
        # 3. Download comments.csv
        # 4. Verify internal comments ARE in CSV
        pass

    async def test_auditor_cannot_set_is_internal_true(self, client: AsyncClient):
        """Auditor attempting to create is_internal=true comment should be forbidden."""
        # TODO: Implement
        # 1. Login as auditor
        # 2. POST comment with is_internal=true
        # 3. Expect 403 Forbidden
        pass
