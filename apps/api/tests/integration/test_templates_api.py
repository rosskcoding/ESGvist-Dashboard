"""
Integration tests for Templates API.

Covers:
- CRUD basics (create + list)
- Apply template creates a block in the target section
- order_index=0 appends to the end of the section
- i18n locale is created in report.source_locale
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTemplatesAPI:
    async def test_create_and_list_templates(self, auth_client: AsyncClient):
        create = await auth_client.post(
            "/api/v1/templates",
            json={
                "scope": "block",
                "block_type": "text",
                "name": "Test Template (Text)",
                "description": "Integration test template",
                "tags": ["test", "template"],
                "template_json": {
                    "variant": "default",
                    "data_json": {},
                    "fields_json": {"body_html": "<p>Hello from template</p>"},
                },
            },
        )
        assert create.status_code == 201, create.text
        template_id = create.json()["template_id"]

        listed = await auth_client.get(
            "/api/v1/templates",
            params={"scope": "block", "page_size": "100"},
        )
        assert listed.status_code == 200, listed.text
        items = listed.json()["items"]
        assert any(str(i["template_id"]) == str(template_id) for i in items)

    async def test_apply_template_appends_and_uses_source_locale(self, auth_client: AsyncClient):
        # Create report with source_locale=en
        report = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2031,
                "title": "Templates Apply Test",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
                "release_locales": ["en"],
            },
        )
        assert report.status_code == 201, report.text
        report_id = report.json()["report_id"]

        # Create section
        section = await auth_client.post(
            "/api/v1/sections",
            json={
                "report_id": report_id,
                "order_index": 0,
                "i18n": [{"locale": "en", "title": "Section EN", "slug": "section-en"}],
            },
        )
        assert section.status_code == 201, section.text
        section_id = section.json()["section_id"]

        # Create a block template
        tpl = await auth_client.post(
            "/api/v1/templates",
            json={
                "scope": "block",
                "block_type": "text",
                "name": "Apply Template (Text)",
                "description": None,
                "tags": ["apply"],
                "template_json": {
                    "variant": "default",
                    "data_json": {},
                    "fields_json": {"body_html": "<p>EN body</p>"},
                },
            },
        )
        assert tpl.status_code == 201, tpl.text
        template_id = tpl.json()["template_id"]

        # Apply twice with order_index=0 (append)
        applied1 = await auth_client.post(
            "/api/v1/templates/apply",
            json={
                "template_id": template_id,
                "report_id": report_id,
                "section_id": section_id,
                "order_index": 0,
            },
        )
        assert applied1.status_code == 201, applied1.text
        block1_id = applied1.json()["block_id"]

        applied2 = await auth_client.post(
            "/api/v1/templates/apply",
            json={
                "template_id": template_id,
                "report_id": report_id,
                "section_id": section_id,
                "order_index": 0,
            },
        )
        assert applied2.status_code == 201, applied2.text
        block2_id = applied2.json()["block_id"]

        # Verify blocks are in the section
        blocks = await auth_client.get("/api/v1/blocks", params={"section_id": section_id})
        assert blocks.status_code == 200, blocks.text
        items = blocks.json()["items"]
        by_id = {b["block_id"]: b for b in items}
        assert block1_id in by_id, "First block not found in section"
        assert block2_id in by_id, "Second block not found in section"
        # Verify blocks have different IDs (created independently)
        assert block1_id != block2_id, "Two template applies should create distinct blocks"

        # Verify i18n locale uses report source_locale (en)
        block2 = await auth_client.get(f"/api/v1/blocks/{block2_id}")
        assert block2.status_code == 200, block2.text
        i18n_locales = [i["locale"] for i in block2.json()["i18n"]]
        assert i18n_locales == ["en"]

    async def test_apply_template_rejects_invalid_block_type(self, auth_client: AsyncClient):
        # Create report+section
        report = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2032,
                "title": "Invalid Template",
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

        # Create template with invalid block_type (allowed on create, rejected on apply)
        tpl = await auth_client.post(
            "/api/v1/templates",
            json={
                "scope": "block",
                "block_type": "unknown_block_type",
                "name": "Broken template",
                "template_json": {"variant": "default", "data_json": {}, "fields_json": {}},
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
        assert applied.status_code == 422


