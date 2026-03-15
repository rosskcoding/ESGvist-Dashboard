"""
Unit tests for template seeds.

Verifies:
- ALL_TEMPLATES contains exactly 25 templates
- 12 new templates with ASK/AUTO/OPT placeholders are present
- All templates have required fields
"""

import pytest
from app.seeds.templates import ALL_TEMPLATES


class TestTemplateSeeds:
    """Test template seed data structure."""

    def test_total_template_count(self):
        """Verify total count is 25 (13 legacy + 12 new)."""
        assert len(ALL_TEMPLATES) == 25, f"Expected 25 templates, got {len(ALL_TEMPLATES)}"

    def test_new_templates_present(self):
        """Verify all 12 new templates are in ALL_TEMPLATES."""
        new_template_names = {
            "CEO Message",
            "Callout Box",
            "Downloads Section",
            "Emissions by Scope",
            "Water Usage Trend",
            "Energy Mix",
            "SASB Index",
            "SDG Alignment",
            "Board Composition",
            "Governance KPIs",
            "Community Investment",
            "Diversity & Inclusion",
        }

        all_names = {t["name"] for t in ALL_TEMPLATES}

        missing = new_template_names - all_names
        assert not missing, f"Missing new templates: {missing}"

    def test_all_templates_have_required_fields(self):
        """Verify all templates have required structure."""
        required_fields = {"template_id", "scope", "block_type", "name", "template_json", "is_system"}

        for template in ALL_TEMPLATES:
            missing = required_fields - set(template.keys())
            assert not missing, f"Template '{template.get('name', 'unknown')}' missing fields: {missing}"

    def test_all_templates_are_system_templates(self):
        """Verify all seeded templates are system templates."""
        for template in ALL_TEMPLATES:
            assert template["is_system"] is True, f"Template '{template['name']}' should be system template"

    def test_template_json_structure(self):
        """Verify template_json has required structure."""
        for template in ALL_TEMPLATES:
            template_json = template["template_json"]
            assert "variant" in template_json, f"Template '{template['name']}' missing 'variant'"
            assert "data_json" in template_json, f"Template '{template['name']}' missing 'data_json'"
            assert "fields_json" in template_json, f"Template '{template['name']}' missing 'fields_json'"

    def test_new_templates_use_placeholder_format(self):
        """Verify new templates use ASK/AUTO/OPT/REF placeholder format."""
        new_template_names = {
            "CEO Message",
            "Callout Box",
            "Downloads Section",
            "Emissions by Scope",
            "Water Usage Trend",
            "Energy Mix",
            "SASB Index",
            "SDG Alignment",
            "Board Composition",
            "Governance KPIs",
            "Community Investment",
            "Diversity & Inclusion",
        }

        import json

        for template in ALL_TEMPLATES:
            if template["name"] not in new_template_names:
                continue

            # Check if template_json contains placeholder strings
            template_json_str = json.dumps(template["template_json"])

            # At least one placeholder should be present in new templates
            has_placeholder = (
                "[[ASK:" in template_json_str
                or "[[AUTO:" in template_json_str
                or "[[OPT:" in template_json_str
                or "[[REF:" in template_json_str
            )

            assert has_placeholder, (
                f"New template '{template['name']}' should contain "
                "ASK/AUTO/OPT/REF placeholders"
            )

    def test_template_categories(self):
        """Verify templates are distributed across expected categories."""
        by_type = {}
        for template in ALL_TEMPLATES:
            block_type = template.get("block_type") or "other"
            by_type[block_type] = by_type.get(block_type, 0) + 1

        # Expected distribution (approximate)
        assert by_type.get("kpi_cards", 0) >= 7, "Should have at least 7 KPI templates"
        assert by_type.get("chart", 0) >= 7, "Should have at least 7 Chart templates"
        assert by_type.get("table", 0) >= 6, "Should have at least 6 Table templates"
        assert by_type.get("timeline", 0) >= 2, "Should have at least 2 Timeline templates"
        assert by_type.get("quote", 0) >= 1, "Should have at least 1 Quote template"
        assert by_type.get("text", 0) >= 1, "Should have at least 1 Text template"
        assert by_type.get("downloads", 0) >= 1, "Should have at least 1 Downloads template"




