"""
Unit tests for Comment threads and comments.

Tests:
- Thread creation and status
- Comment append-only
- Resolve/reopen functionality
- Soft delete
"""

import pytest
from uuid import uuid4

from app.domain.models import Comment, CommentThread, LockScopeType, ThreadStatus


class TestCommentThreadModel:
    """Test CommentThread model and methods."""

    def test_create_thread(self):
        """Test creating a comment thread."""
        thread = CommentThread(
            company_id=uuid4(),
            report_id=uuid4(),
            anchor_type=LockScopeType.BLOCK,
            anchor_id=uuid4(),
            sub_anchor_type="table",
            sub_anchor_key="emissions-table",
            sub_anchor_label="Emissions Table 2024",
            status=ThreadStatus.OPEN,
            created_by=uuid4(),
        )

        assert thread.is_open
        assert not thread.is_resolved
        assert thread.sub_anchor_label == "Emissions Table 2024"

    def test_resolve_thread(self):
        """Test resolving a thread."""
        thread = CommentThread(
            company_id=uuid4(),
            report_id=uuid4(),
            anchor_type=LockScopeType.BLOCK,
            anchor_id=uuid4(),
            status=ThreadStatus.OPEN,
            created_by=uuid4(),
        )

        resolver_id = uuid4()

        assert thread.is_open

        thread.resolve(resolver_id)

        assert thread.is_resolved
        assert thread.resolved_by == resolver_id
        assert thread.resolved_at is not None

    def test_reopen_thread(self):
        """Test reopening a resolved thread."""
        thread = CommentThread(
            company_id=uuid4(),
            report_id=uuid4(),
            anchor_type=LockScopeType.BLOCK,
            anchor_id=uuid4(),
            status=ThreadStatus.RESOLVED,
            created_by=uuid4(),
        )

        # Manually set resolved fields
        resolver_id = uuid4()
        thread.resolved_by = resolver_id
        from datetime import UTC, datetime
        thread.resolved_at = datetime.now(UTC)

        thread.reopen()

        assert thread.is_open
        assert thread.resolved_by is None
        assert thread.resolved_at is None


class TestCommentModel:
    """Test Comment model."""

    def test_create_comment(self):
        """Test creating a comment."""
        comment = Comment(
            thread_id=uuid4(),
            company_id=uuid4(),
            author_user_id=uuid4(),
            author_role_snapshot="editor",
            body="This needs clarification.",
            is_internal=False,
        )

        assert comment.body == "This needs clarification."
        assert comment.author_role_snapshot == "editor"
        assert not comment.is_internal
        assert not comment.is_deleted

    def test_internal_comment(self):
        """Test internal comment (team-only)."""
        comment = Comment(
            thread_id=uuid4(),
            company_id=uuid4(),
            author_user_id=uuid4(),
            author_role_snapshot="editor",
            body="Internal discussion.",
            is_internal=True,
        )

        assert comment.is_internal
        assert not comment.is_deleted

    def test_soft_delete_comment(self):
        """Test soft deleting a comment."""
        comment = Comment(
            thread_id=uuid4(),
            company_id=uuid4(),
            author_user_id=uuid4(),
            author_role_snapshot="auditor",
            body="Test comment",
            is_internal=False,
        )

        deleter_id = uuid4()

        assert not comment.is_deleted

        comment.soft_delete(deleter_id)

        assert comment.is_deleted
        assert comment.deleted_by == deleter_id
        assert comment.deleted_at is not None


