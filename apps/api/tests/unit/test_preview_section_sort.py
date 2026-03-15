"""
Unit tests for preview section sorting.

These tests cover `_sort_sections_hierarchically()` used by the Preview API
to build a deterministic Table of Contents order that matches the admin structure.
"""

from uuid import UUID, uuid4

from app.api.v1.preview import _sort_sections_hierarchically
from app.domain.models import Section


def _make_section(
    *,
    section_id: UUID,
    parent_section_id: UUID | None,
    order_index: int,
) -> Section:
    # Only the fields used by the sorter are required.
    return Section(
        section_id=section_id,
        report_id=uuid4(),
        parent_section_id=parent_section_id,
        order_index=order_index,
        depth=0,
    )


def test_sort_sections_hierarchically_orders_roots_and_children():
    root_a_id = UUID("00000000-0000-0000-0000-000000000001")
    root_b_id = UUID("00000000-0000-0000-0000-000000000002")
    child_a1_id = UUID("00000000-0000-0000-0000-000000000010")
    child_a2_id = UUID("00000000-0000-0000-0000-000000000011")
    grandchild_a1_id = UUID("00000000-0000-0000-0000-000000000020")

    root_a = _make_section(section_id=root_a_id, parent_section_id=None, order_index=0)
    root_b = _make_section(section_id=root_b_id, parent_section_id=None, order_index=1)

    child_a1 = _make_section(section_id=child_a1_id, parent_section_id=root_a_id, order_index=0)
    child_a2 = _make_section(section_id=child_a2_id, parent_section_id=root_a_id, order_index=1)
    grandchild_a1 = _make_section(section_id=grandchild_a1_id, parent_section_id=child_a1_id, order_index=0)

    unsorted = [child_a2, root_b, grandchild_a1, root_a, child_a1]
    sorted_sections = _sort_sections_hierarchically(unsorted)

    assert [s.section_id for s in sorted_sections] == [
        root_a_id,
        child_a1_id,
        grandchild_a1_id,
        child_a2_id,
        root_b_id,
    ]


def test_sort_sections_hierarchically_breaks_ties_by_section_id():
    # When siblings share the same order_index, the sort must be deterministic.
    root_1_id = UUID("00000000-0000-0000-0000-000000000001")
    root_2_id = UUID("00000000-0000-0000-0000-000000000002")

    root_1 = _make_section(section_id=root_1_id, parent_section_id=None, order_index=0)
    root_2 = _make_section(section_id=root_2_id, parent_section_id=None, order_index=0)

    sorted_sections = _sort_sections_hierarchically([root_2, root_1])
    assert [s.section_id for s in sorted_sections] == [root_1_id, root_2_id]



