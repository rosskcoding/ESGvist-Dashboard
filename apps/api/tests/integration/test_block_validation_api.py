"""
Integration tests for Block Validation endpoint.

Endpoint:
POST /api/v1/blocks/{block_id}/validate?locale=ru
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestBlockValidationAPI:
    async def test_validate_text_block_ok(self, auth_client: AsyncClient):
        # Setup report + section
        report = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2033,
                "title": "Validation Test",
                "source_locale": "ru",
                "default_locale": "ru",
                "enabled_locales": ["ru"],
            },
        )
        assert report.status_code == 201, report.text
        report_id = report.json()["report_id"]

        section = await auth_client.post(
            "/api/v1/sections",
            json={
                "report_id": report_id,
                "order_index": 0,
                "i18n": [{"locale": "ru", "title": "S", "slug": "s"}],
            },
        )
        assert section.status_code == 201, section.text
        section_id = section.json()["section_id"]

        # Template → apply → get block_id
        tpl = await auth_client.post(
            "/api/v1/templates",
            json={
                "scope": "block",
                "block_type": "text",
                "name": "Text template for validation",
                "template_json": {
                    "variant": "default",
                    "data_json": {},
                    "fields_json": {"body_html": "<p>OK</p>"},
                },
            },
        )
        assert tpl.status_code == 201, tpl.text
        template_id = tpl.json()["template_id"]

        applied = await auth_client.post(
            "/api/v1/templates/apply",
            json={
                "template_id": template_id,
                "report_id": report_id,
                "section_id": section_id,
                "order_index": 0,
            },
        )
        assert applied.status_code == 201, applied.text
        block_id = applied.json()["block_id"]

        # Validate
        resp = await auth_client.post(f"/api/v1/blocks/{block_id}/validate", params={"locale": "ru"})
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["can_publish"] is True
        assert payload["error_count"] == 0

    async def test_validate_chart_requires_insight_text(self, auth_client: AsyncClient):
        # Setup report + section
        report = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2034,
                "title": "Chart Validation Test",
                "source_locale": "ru",
                "default_locale": "ru",
                "enabled_locales": ["ru"],
            },
        )
        assert report.status_code == 201, report.text
        report_id = report.json()["report_id"]

        section = await auth_client.post(
            "/api/v1/sections",
            json={
                "report_id": report_id,
                "order_index": 0,
                "i18n": [{"locale": "ru", "title": "S", "slug": "s"}],
            },
        )
        assert section.status_code == 201, section.text
        section_id = section.json()["section_id"]

        # Chart template WITHOUT insight_text
        tpl = await auth_client.post(
            "/api/v1/templates",
            json={
                "scope": "block",
                "block_type": "chart",
                "name": "Chart template missing insight_text",
                "template_json": {
                    "variant": "default",
                    "data_json": {
                        "chart_type": "bar",
                        "data_source": {
                            "type": "inline",
                            "inline_series": [
                                {"key": "s1", "data": [{"x": "2024", "y": 1}]}
                            ],
                        },
                        "options": {},
                    },
                    "fields_json": {"caption": "C", "insight_text": ""},
                },
            },
        )
        assert tpl.status_code == 201, tpl.text
        template_id = tpl.json()["template_id"]

        applied = await auth_client.post(
            "/api/v1/templates/apply",
            json={
                "template_id": template_id,
                "report_id": report_id,
                "section_id": section_id,
                "order_index": 0,
            },
        )
        assert applied.status_code == 201, applied.text
        block_id = applied.json()["block_id"]

        resp = await auth_client.post(f"/api/v1/blocks/{block_id}/validate", params={"locale": "ru"})
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["can_publish"] is False
        assert payload["error_count"] >= 1
        assert any(i["code"] == "REQUIRED_INSIGHT" for i in payload["issues"])

    async def test_validate_rejects_invalid_locale(self, auth_client: AsyncClient, test_section_id: str, test_report_id: str):
        # Create any block via template apply
        tpl = await auth_client.post(
            "/api/v1/templates",
            json={
                "scope": "block",
                "block_type": "text",
                "name": "Locale validation template",
                "template_json": {"variant": "default", "data_json": {}, "fields_json": {"body_html": "<p>x</p>"}},
            },
        )
        assert tpl.status_code == 201, tpl.text
        template_id = tpl.json()["template_id"]

        applied = await auth_client.post(
            "/api/v1/templates/apply",
            json={
                "template_id": template_id,
                "report_id": test_report_id,
                "section_id": test_section_id,
                "order_index": 0,
            },
        )
        assert applied.status_code == 201, applied.text
        block_id = applied.json()["block_id"]

        resp = await auth_client.post(f"/api/v1/blocks/{block_id}/validate", params={"locale": "fr"})
        assert resp.status_code == 422





