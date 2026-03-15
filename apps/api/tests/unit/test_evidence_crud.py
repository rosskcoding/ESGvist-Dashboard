"""
Unit tests for Evidence CRUD and status transitions.

Tests:
- Evidence creation with all fields
- Status transitions (provided → reviewed → issue → resolved)
- Soft delete
- Sub-anchor fields
"""

import pytest
from datetime import date
from uuid import uuid4

from app.domain.models import (
    EvidenceItem,
    EvidenceStatus,
    EvidenceType,
    EvidenceVisibility,
    LockScopeType,
)


class TestEvidenceModel:
    """Test Evidence model and methods."""

    def test_create_evidence_with_all_fields(self):
        """Test creating evidence with all new fields."""
        company_id = uuid4()
        report_id = uuid4()
        block_id = uuid4()
        owner_id = uuid4()
        created_by = uuid4()

        evidence = EvidenceItem(
            company_id=company_id,
            report_id=report_id,
            scope_type=LockScopeType.BLOCK,
            scope_id=block_id,
            sub_anchor_type="table",
            sub_anchor_key="emissions-2024",
            sub_anchor_label="Emissions Table Q4 2024",
            type=EvidenceType.FILE,
            title="Emissions Data Export",
            description="Verified emissions data from ERP",
            status=EvidenceStatus.PROVIDED,
            owner_user_id=owner_id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            version_label="ERP export v2.1",
            visibility=EvidenceVisibility.AUDIT,
            asset_id=uuid4(),
            created_by=created_by,
        )

        assert evidence.status == EvidenceStatus.PROVIDED
        assert evidence.sub_anchor_type == "table"
        assert evidence.sub_anchor_label == "Emissions Table Q4 2024"
        assert evidence.owner_user_id == owner_id
        assert evidence.version_label == "ERP export v2.1"
        assert not evidence.is_deleted

    def test_soft_delete(self):
        """Test soft delete functionality."""
        evidence = EvidenceItem(
            company_id=uuid4(),
            report_id=uuid4(),
            scope_type=LockScopeType.BLOCK,
            scope_id=uuid4(),
            type=EvidenceType.NOTE,
            title="Test Evidence",
            note_md="Test note",
            created_by=uuid4(),
        )

        deleter_id = uuid4()

        assert not evidence.is_deleted

        evidence.soft_delete(deleter_id)

        assert evidence.is_deleted
        assert evidence.deleted_by == deleter_id
        assert evidence.deleted_at is not None

    def test_status_workflow(self):
        """Test status transitions."""
        evidence = EvidenceItem(
            company_id=uuid4(),
            report_id=uuid4(),
            scope_type=LockScopeType.BLOCK,
            scope_id=uuid4(),
            type=EvidenceType.LINK,
            title="Test Evidence",
            url="https://example.com",
            status=EvidenceStatus.PROVIDED,
            created_by=uuid4(),
        )

        # Transition: provided → reviewed
        assert evidence.status == EvidenceStatus.PROVIDED
        evidence.status = EvidenceStatus.REVIEWED
        assert evidence.status == EvidenceStatus.REVIEWED

        # Transition: reviewed → issue
        evidence.status = EvidenceStatus.ISSUE
        assert evidence.status == EvidenceStatus.ISSUE

        # Transition: issue → resolved
        evidence.status = EvidenceStatus.RESOLVED
        assert evidence.status == EvidenceStatus.RESOLVED

    def test_visibility_properties(self):
        """Test visibility helper properties."""
        team_evidence = EvidenceItem(
            company_id=uuid4(),
            report_id=uuid4(),
            scope_type=LockScopeType.BLOCK,
            scope_id=uuid4(),
            type=EvidenceType.NOTE,
            title="Team Evidence",
            note_md="Internal note",
            visibility=EvidenceVisibility.TEAM,
            created_by=uuid4(),
        )

        assert team_evidence.is_visible_to_team
        assert not team_evidence.is_visible_to_auditors

        audit_evidence = EvidenceItem(
            company_id=uuid4(),
            report_id=uuid4(),
            scope_type=LockScopeType.BLOCK,
            scope_id=uuid4(),
            type=EvidenceType.NOTE,
            title="Audit Evidence",
            note_md="Public note",
            visibility=EvidenceVisibility.AUDIT,
            created_by=uuid4(),
        )

        assert audit_evidence.is_visible_to_team
        assert audit_evidence.is_visible_to_auditors

