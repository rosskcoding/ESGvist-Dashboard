"""
Unit tests for Section-related functionality.

Tests for:
- Section structure fields (depth, label_prefix, label_suffix)
- Bulk reorder validation
- Section hierarchy constraints
"""

import pytest
from uuid import uuid4

from pydantic import ValidationError

from app.domain.schemas.section import (
    SectionCreate,
    SectionUpdate,
    SectionDTO,
    SectionReorderItem,
    BulkReorderRequest,
)


class TestSectionStructureFields:
    """Tests for section structure fields validation."""

    def test_section_create_with_defaults(self):
        """Section should have default depth=0, label_prefix=None, label_suffix=None."""
        data = SectionCreate(
            report_id=uuid4(),
            i18n=[{
                "locale": "ru",
                "title": "Test Section",
                "slug": "test-section",
            }],
        )
        assert data.depth == 0
        assert data.label_prefix is None
        assert data.label_suffix is None

    def test_section_create_with_structure_fields(self):
        """Section can be created with structure fields."""
        data = SectionCreate(
            report_id=uuid4(),
            depth=1,
            label_prefix="09",
            label_suffix="(p. 10)",
            i18n=[{
                "locale": "ru",
                "title": "Test Section",
                "slug": "test-section",
            }],
        )
        assert data.depth == 1
        assert data.label_prefix == "09"
        assert data.label_suffix == "(p. 10)"

    def test_section_depth_max_value(self):
        """Section depth cannot exceed 3 (4 levels: 0-3)."""
        with pytest.raises(ValidationError) as exc_info:
            SectionCreate(
                report_id=uuid4(),
                depth=4,  # Invalid: max is 3
                i18n=[{
                    "locale": "ru",
                    "title": "Test",
                    "slug": "test",
                }],
            )
        assert "depth" in str(exc_info.value)

    def test_section_depth_min_value(self):
        """Section depth cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            SectionCreate(
                report_id=uuid4(),
                depth=-1,  # Invalid: min is 0
                i18n=[{
                    "locale": "ru",
                    "title": "Test",
                    "slug": "test",
                }],
            )
        assert "depth" in str(exc_info.value)

    def test_label_prefix_max_length(self):
        """label_prefix cannot exceed 20 characters."""
        with pytest.raises(ValidationError) as exc_info:
            SectionCreate(
                report_id=uuid4(),
                label_prefix="x" * 21,  # Invalid: max is 20
                i18n=[{
                    "locale": "ru",
                    "title": "Test",
                    "slug": "test",
                }],
            )
        assert "label_prefix" in str(exc_info.value)

    def test_label_suffix_max_length(self):
        """label_suffix cannot exceed 50 characters."""
        with pytest.raises(ValidationError) as exc_info:
            SectionCreate(
                report_id=uuid4(),
                label_suffix="x" * 51,  # Invalid: max is 50
                i18n=[{
                    "locale": "ru",
                    "title": "Test",
                    "slug": "test",
                }],
            )
        assert "label_suffix" in str(exc_info.value)

    def test_section_update_structure_fields(self):
        """Section update can modify structure fields."""
        data = SectionUpdate(
            depth=2,
            label_prefix="1.1",
            label_suffix="(p. 5)",
        )
        assert data.depth == 2
        assert data.label_prefix == "1.1"
        assert data.label_suffix == "(p. 5)"


class TestSectionReorderItem:
    """Tests for SectionReorderItem schema."""

    def test_valid_reorder_item(self):
        """Valid reorder item with all fields."""
        item = SectionReorderItem(
            section_id=uuid4(),
            order_index=0,
            parent_section_id=None,
            depth=0,
        )
        assert item.order_index == 0
        assert item.parent_section_id is None
        assert item.depth == 0

    def test_reorder_item_with_parent(self):
        """Reorder item with parent section."""
        parent_id = uuid4()
        item = SectionReorderItem(
            section_id=uuid4(),
            order_index=2,
            parent_section_id=parent_id,
            depth=1,
        )
        assert item.parent_section_id == parent_id
        assert item.depth == 1

    def test_reorder_item_invalid_depth(self):
        """Reorder item depth must be 0-3."""
        with pytest.raises(ValidationError) as exc_info:
            SectionReorderItem(
                section_id=uuid4(),
                order_index=0,
                parent_section_id=None,
                depth=4,  # Invalid
            )
        assert "depth" in str(exc_info.value)

    def test_reorder_item_invalid_order_index(self):
        """Reorder item order_index must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            SectionReorderItem(
                section_id=uuid4(),
                order_index=-1,  # Invalid
                parent_section_id=None,
                depth=0,
            )
        assert "order_index" in str(exc_info.value)


class TestBulkReorderRequest:
    """Tests for BulkReorderRequest schema."""

    def test_valid_bulk_reorder(self):
        """Valid bulk reorder request."""
        report_id = uuid4()
        request = BulkReorderRequest(
            report_id=report_id,
            items=[
                SectionReorderItem(
                    section_id=uuid4(),
                    order_index=0,
                    parent_section_id=None,
                    depth=0,
                ),
                SectionReorderItem(
                    section_id=uuid4(),
                    order_index=1,
                    parent_section_id=None,
                    depth=0,
                ),
            ],
        )
        assert request.report_id == report_id
        assert len(request.items) == 2

    def test_bulk_reorder_empty_items(self):
        """Bulk reorder requires at least one item."""
        with pytest.raises(ValidationError) as exc_info:
            BulkReorderRequest(
                report_id=uuid4(),
                items=[],  # Invalid: min_length=1
            )
        assert "items" in str(exc_info.value)

    def test_bulk_reorder_single_item(self):
        """Bulk reorder with single item is valid."""
        request = BulkReorderRequest(
            report_id=uuid4(),
            items=[
                SectionReorderItem(
                    section_id=uuid4(),
                    order_index=0,
                    parent_section_id=None,
                    depth=0,
                ),
            ],
        )
        assert len(request.items) == 1


class TestSectionDTO:
    """Tests for SectionDTO schema."""

    def test_section_dto_with_structure_fields(self):
        """SectionDTO includes structure fields."""
        from datetime import datetime, UTC

        dto = SectionDTO(
            section_id=uuid4(),
            report_id=uuid4(),
            order_index=0,
            parent_section_id=None,
            depth=1,
            label_prefix="1.",
            label_suffix="(p. 5)",
            created_at_utc=datetime.now(UTC),
            updated_at_utc=datetime.now(UTC),
            i18n=[],
            blocks_count=5,
        )
        assert dto.depth == 1
        assert dto.label_prefix == "1."
        assert dto.label_suffix == "(p. 5)"
        assert dto.blocks_count == 5



