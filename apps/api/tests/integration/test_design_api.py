"""
Integration tests for Design API endpoints.

Tests design settings CRUD, presets API, and block preset overrides.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestDesignSettingsAPI:
    """Tests for /reports/{report_id}/design endpoints."""

    @pytest.mark.asyncio
    async def test_get_design_returns_defaults(self, auth_client: AsyncClient, test_report_id: str):
        """GET /reports/{id}/design should return default settings for new report."""
        resp = await auth_client.get(f"/api/v1/reports/{test_report_id}/design")
        assert resp.status_code == 200

        data = resp.json()
        # Should have all expected fields with defaults
        assert "theme_slug" in data
        assert "layout" in data
        assert "typography" in data
        assert "block_type_presets" in data
        assert "block_overrides" in data

        # block_overrides should be empty dict by default
        assert data["block_overrides"] == {}

    @pytest.mark.asyncio
    async def test_get_design_report_not_found(self, auth_client: AsyncClient):
        """GET /reports/{id}/design should return 404 for nonexistent report."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.get(f"/api/v1/reports/{fake_id}/design")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_design_updates_theme(self, auth_client: AsyncClient, test_report_id: str):
        """PATCH /reports/{id}/design should update theme_slug."""
        resp = await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={"theme_slug": "dark"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["theme_slug"] == "dark"

        # Verify persisted
        resp2 = await auth_client.get(f"/api/v1/reports/{test_report_id}/design")
        assert resp2.json()["theme_slug"] == "dark"

    @pytest.mark.asyncio
    async def test_patch_design_updates_block_type_presets(
        self, auth_client: AsyncClient, test_report_id: str
    ):
        """PATCH should update block_type_presets."""
        resp = await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={
                "block_type_presets": {
                    "kpi_cards": "inline",
                    "table": "compact",
                }
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["block_type_presets"]["kpi_cards"] == "inline"
        assert data["block_type_presets"]["table"] == "compact"

    @pytest.mark.asyncio
    async def test_patch_design_invalid_preset_rejected(
        self, auth_client: AsyncClient, test_report_id: str
    ):
        """PATCH with invalid preset should return 400."""
        resp = await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={
                "block_type_presets": {
                    "kpi_cards": "nonexistent_preset",
                }
            },
        )
        assert resp.status_code == 400
        assert "Invalid preset" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_patch_design_preserves_other_fields(
        self, auth_client: AsyncClient, test_report_id: str
    ):
        """PATCH should preserve fields not in update."""
        # First set theme
        await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={"theme_slug": "custom-theme"},
        )

        # Then update presets (without theme)
        resp = await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={"block_type_presets": {"kpi_cards": "big_number"}},
        )
        assert resp.status_code == 200

        data = resp.json()
        # Theme should be preserved
        assert data["theme_slug"] == "custom-theme"
        # Presets should be updated
        assert data["block_type_presets"]["kpi_cards"] == "big_number"

    @pytest.mark.asyncio
    async def test_put_design_replaces_all(self, auth_client: AsyncClient, test_report_id: str):
        """PUT /reports/{id}/design should replace all settings."""
        full_settings = {
            "theme_slug": "new-theme",
            "font_mode": "portable",
            "package_mode_default": "portable",
            "layout": {
                "preset": "topnav",
                "container_width": "wide",
                "section_spacing": "airy",
                "show_toc": False,
            },
            "typography": {
                "font_family_body": "Georgia",
                "font_family_heading": "Helvetica",
                "font_family_mono": "Fira Code",
                "base_font_size": 18,
                "heading_scale": "large",
            },
            "block_type_presets": {
                "kpi_cards": "minimal",
                "table": "bordered",
            },
            "block_overrides": {},
        }

        resp = await auth_client.put(
            f"/api/v1/reports/{test_report_id}/design",
            json=full_settings,
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["theme_slug"] == "new-theme"
        assert data["layout"]["preset"] == "topnav"
        assert data["typography"]["base_font_size"] == 18


class TestPresetsAPI:
    """Tests for /design/presets endpoints."""

    @pytest.mark.asyncio
    async def test_get_all_presets(self, auth_client: AsyncClient):
        """GET /design/presets should return all available presets."""
        resp = await auth_client.get("/api/v1/design/presets")
        assert resp.status_code == 200

        data = resp.json()
        assert "presets" in data
        assert "defaults" in data

        # Should have presets for known block types
        assert "kpi_cards" in data["presets"]
        assert "table" in data["presets"]
        assert "quote" in data["presets"]

        # Defaults should match presets
        for block_type, default in data["defaults"].items():
            assert default in data["presets"][block_type]

    @pytest.mark.asyncio
    async def test_get_presets_for_block_type(self, auth_client: AsyncClient):
        """GET /design/presets/{block_type} should return presets with descriptions."""
        resp = await auth_client.get("/api/v1/design/presets/kpi_cards")
        assert resp.status_code == 200

        data = resp.json()
        assert data["block_type"] == "kpi_cards"
        assert "default" in data
        assert "presets" in data
        assert len(data["presets"]) >= 3

        # Each preset should have name and description
        for preset in data["presets"]:
            assert "name" in preset
            assert "description" in preset or preset["description"] is None

    @pytest.mark.asyncio
    async def test_get_presets_unknown_block_type(self, auth_client: AsyncClient):
        """GET /design/presets/{unknown_type} should return 404."""
        resp = await auth_client.get("/api/v1/design/presets/unknown_block_type")
        assert resp.status_code == 404


class TestBlockPresetOverrideAPI:
    """Tests for block-level preset override endpoints."""

    @pytest_asyncio.fixture
    async def test_block_id(
        self, auth_client: AsyncClient, test_report_id: str, test_section_id: str
    ) -> str:
        """Create a test block and return its ID."""
        resp = await auth_client.post(
            "/api/v1/blocks",
            json={
                "report_id": test_report_id,
                "section_id": test_section_id,
                "type": "kpi_cards",
                "variant": "default",
                "order_index": 0,
                "data_json": {"cards": []},
                "i18n": [{"locale": "ru", "fields_json": {"cards": []}}],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["block_id"]

    @pytest.mark.asyncio
    async def test_get_block_preset_default(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """GET /reports/{id}/blocks/{block_id}/preset should return system default."""
        resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["block_id"] == test_block_id
        assert data["block_type"] == "kpi_cards"
        assert data["preset"] == "cards"  # system default
        assert data["source"] == "system_default"

    @pytest.mark.asyncio
    async def test_set_block_preset_override(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """PUT /reports/{id}/blocks/{block_id}/preset should set override."""
        resp = await auth_client.put(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset",
            params={"preset": "big_number"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["preset"] == "big_number"
        assert data["source"] == "block_override"

        # Verify persisted
        resp2 = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset"
        )
        assert resp2.json()["preset"] == "big_number"
        assert resp2.json()["source"] == "block_override"

    @pytest.mark.asyncio
    async def test_set_invalid_preset_rejected(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """PUT with invalid preset should return 400."""
        resp = await auth_client.put(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset",
            params={"preset": "invalid_preset"},
        )
        assert resp.status_code == 400
        assert "Invalid preset" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_set_wrong_type_preset_rejected(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """PUT with preset from wrong block type should return 400."""
        # "striped" is for table, not kpi_cards
        resp = await auth_client.put(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset",
            params={"preset": "striped"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_block_preset_override(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """DELETE /reports/{id}/blocks/{block_id}/preset should remove override."""
        # First set an override
        await auth_client.put(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset",
            params={"preset": "inline"},
        )

        # Then delete it
        resp = await auth_client.delete(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["preset"] == "cards"  # Back to system default
        assert data["source"] in ["type_preset", "system_default"]

    @pytest.mark.asyncio
    async def test_block_not_found(self, auth_client: AsyncClient, test_report_id: str):
        """GET/PUT/DELETE with nonexistent block should return 404."""
        fake_block_id = "00000000-0000-0000-0000-000000000000"

        resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/blocks/{fake_block_id}/preset"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_type_preset_takes_precedence_over_system(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """Type preset should be used if no block override."""
        # Set type preset for kpi_cards
        await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={"block_type_presets": {"kpi_cards": "minimal"}},
        )

        # Get block preset (no block override)
        resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["preset"] == "minimal"
        assert data["source"] == "type_preset"

    @pytest.mark.asyncio
    async def test_block_override_takes_precedence_over_type(
        self, auth_client: AsyncClient, test_report_id: str, test_block_id: str
    ):
        """Block override should take precedence over type preset."""
        # Set type preset
        resp1 = await auth_client.patch(
            f"/api/v1/reports/{test_report_id}/design",
            json={"block_type_presets": {"kpi_cards": "minimal"}},
        )
        assert resp1.status_code == 200

        # Verify type preset is set
        design1 = await auth_client.get(f"/api/v1/reports/{test_report_id}/design")
        assert design1.json()["block_type_presets"]["kpi_cards"] == "minimal"

        # Set block override
        resp2 = await auth_client.put(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset",
            params={"preset": "grid"},
        )
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["preset"] == "grid"

        # Verify block override is in design_json
        design2 = await auth_client.get(f"/api/v1/reports/{test_report_id}/design")
        assert test_block_id in design2.json()["block_overrides"], \
            f"block_overrides = {design2.json()['block_overrides']}"
        assert design2.json()["block_overrides"][test_block_id] == "grid"

        # Block override should win when getting resolved preset
        resp = await auth_client.get(
            f"/api/v1/reports/{test_report_id}/blocks/{test_block_id}/preset"
        )
        data = resp.json()
        assert data["preset"] == "grid", f"Expected grid but got {data}"
        assert data["source"] == "block_override"

