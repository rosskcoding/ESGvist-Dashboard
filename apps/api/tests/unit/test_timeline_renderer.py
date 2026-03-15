"""
Unit tests for Timeline block rendering.

Tests both data formats:
1. List format: fields.items[] as array (new format)
2. Dict format: fields.events{} as dict keyed by event_id (legacy seed data format)

Regression test for: Jinja2 UndefinedError when events is dict not list
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock

from app.domain.models.enums import BlockType, BlockVariant
from app.services.renderer import Renderer


class TestTimelineBlockRendering:
    """Tests for timeline block template rendering."""

    @pytest.fixture
    def renderer(self):
        """Create renderer instance."""
        return Renderer()

    def _create_mock_block(
        self,
        data_json: dict,
        fields_json: dict,
    ) -> MagicMock:
        """Create a mock timeline block."""
        block = MagicMock()
        block.block_id = uuid4()
        block.type = BlockType.TIMELINE
        block.variant = BlockVariant.DEFAULT
        block.data_json = data_json

        i18n = MagicMock()
        i18n.fields_json = fields_json
        block.get_i18n = MagicMock(return_value=i18n)

        return block

    def test_timeline_with_list_format_items(self, renderer):
        """Test timeline renders correctly with list format items."""
        block = self._create_mock_block(
            data_json={
                "layout": "vertical",
                "items": [
                    {"date": "January 2024", "icon": None},
                    {"date": "July 2024", "icon": None},
                ],
            },
            fields_json={
                "title": "Key events",
                "items": [
                    {"title": "Event 1", "description": "Description 1"},
                    {"title": "Event 2", "description": "Description 2"},
                ],
            },
        )

        html = renderer.render_block(block, "en")

        # Check structure rendered
        assert "rpt-block--timeline" in html
        assert "rpt-timeline--vertical" in html
        assert "Key events" in html
        # Check items rendered
        assert "Event 1" in html
        assert "Event 2" in html
        assert "Description 1" in html
        assert "Description 2" in html

    def test_timeline_with_dict_format_events(self, renderer):
        """
        Test timeline renders correctly with dict format events (keyed by event_id).

        This is the legacy format from seed data where fields.events is a dict:
        {
            "evt_2024_01": {"title": "...", "description": "..."},
            "evt_2024_07": {"title": "...", "description": "..."}
        }

        Regression test for: jinja2.exceptions.UndefinedError: dict object has no element 0
        """
        block = self._create_mock_block(
            data_json={
                "events": [
                    {"event_id": "evt_2024_01", "date_start": "2024", "date_format": "year"},
                    {"event_id": "evt_2024_07", "date_start": "2024-07", "date_format": "month"},
                ],
                "auto_sort": True,
            },
            fields_json={
                "title": "Key milestones",
                "events": {
                    "evt_2024_01": {"title": "Event A", "description": "Event A description"},
                    "evt_2024_07": {"title": "Event B", "description": "Event B description"},
                },
            },
        )

        # This should NOT raise UndefinedError
        html = renderer.render_block(block, "en")

        # Check structure rendered
        assert "rpt-block--timeline" in html
        assert "Key milestones" in html
        # Check events rendered by event_id lookup
        assert "Event A" in html
        assert "Event B" in html
        assert "Event A description" in html
        assert "Event B description" in html

    def test_timeline_with_empty_events(self, renderer):
        """Test timeline handles empty events gracefully."""
        block = self._create_mock_block(
            data_json={"events": [], "layout": "vertical"},
            fields_json={"title": "Empty timeline", "events": {}},
        )

        html = renderer.render_block(block, "en")

        assert "rpt-block--timeline" in html
        assert "Empty timeline" in html
        # Should show placeholder for empty timeline
        assert "No events to display" in html

    def test_timeline_with_missing_event_id_in_dict(self, renderer):
        """Test timeline handles missing event_id in dict gracefully."""
        block = self._create_mock_block(
            data_json={
                "events": [
                    {"event_id": "evt_exists", "date_start": "2024"},
                    {"event_id": "evt_missing", "date_start": "2025"},
                ],
            },
            fields_json={
                "title": "Partial data",
                "events": {
                    "evt_exists": {"title": "Existing event", "description": "Description"},
                    # evt_missing intentionally not in dict
                },
            },
        )

        # Should not crash, should render what it can
        html = renderer.render_block(block, "en")

        assert "Existing event" in html
        # Missing event should render empty title (graceful fallback)
        assert "rpt-timeline__event" in html

    def test_timeline_horizontal_layout(self, renderer):
        """Test timeline with horizontal layout."""
        block = self._create_mock_block(
            data_json={
                "layout": "horizontal",
                "items": [{"date": "2024"}],
            },
            fields_json={
                "items": [{"title": "Event"}],
            },
        )

        html = renderer.render_block(block, "en")

        assert "rpt-timeline--horizontal" in html

    def test_timeline_with_date_label_override(self, renderer):
        """Test timeline uses date_label from i18n if provided."""
        block = self._create_mock_block(
            data_json={
                "items": [{"date": "2024-01-15"}],
            },
            fields_json={
                "items": [{"title": "Event", "date_label": "Mid-January"}],
            },
        )

        html = renderer.render_block(block, "en")

        # Should use date_label instead of raw date
        assert "Mid-January" in html

