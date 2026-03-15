"""
Integration tests for chart export API.

Covers:
- Vega-Lite spec generation endpoint
- Binary export endpoints (SVG/PNG/PDF)
- Export formats list
"""

import pytest
from httpx import AsyncClient


try:
    import vl_convert  # noqa: F401

    HAS_VL_CONVERT = True
except Exception:
    HAS_VL_CONVERT = False


@pytest.mark.asyncio
class TestChartExportAPI:
    async def _create_chart_block(
        self,
        auth_client: AsyncClient,
        *,
        report_id: str,
        section_id: str,
    ) -> str:
        resp = await auth_client.post(
            "/api/v1/blocks",
            json={
                "report_id": report_id,
                "section_id": section_id,
                "type": "chart",
                "variant": "default",
                "order_index": 0,
                "data_json": {
                    "schema_version": 2,
                    "chart_type": "bar",
                    "data_source": {
                        "type": "inline",
                        "inline_data": {
                            "columns": ["category", "value"],
                            "rows": [
                                ["A", 10],
                                ["B", 20],
                            ],
                        },
                    },
                    "mapping": {
                        "x": {"field": "category", "type": "category"},
                        "series": [{"name": "Value", "y_field": "value", "axis": "left"}],
                    },
                    "options": {"show_legend": True, "show_grid": True},
                },
                "i18n": [
                    {
                        "locale": "ru",
                        "fields_json": {
                            "caption": "Test chart caption",
                            "insight_text": "Test insight text for A11Y.",
                        },
                    }
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["block_id"]

    async def _create_text_block(
        self,
        auth_client: AsyncClient,
        *,
        report_id: str,
        section_id: str,
    ) -> str:
        resp = await auth_client.post(
            "/api/v1/blocks",
            json={
                "report_id": report_id,
                "section_id": section_id,
                "type": "text",
                "variant": "default",
                "order_index": 0,
                "data_json": {},
                "i18n": [{"locale": "ru", "fields_json": {"body_html": "<p>Hello</p>"}}],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["block_id"]

    async def test_list_export_formats(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/blocks/chart/export-formats")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        ids = {f["id"] for f in data}
        assert {"svg", "png", "pdf"} <= ids

    async def test_get_vega_spec(self, auth_client: AsyncClient, test_report_id: str, test_section_id: str):
        block_id = await self._create_chart_block(
            auth_client,
            report_id=test_report_id,
            section_id=test_section_id,
        )

        resp = await auth_client.get(
            f"/api/v1/blocks/{block_id}/chart/vega-spec",
            params={"width": 320, "height": 200, "locale": "ru"},
        )
        assert resp.status_code == 200, resp.text
        spec = resp.json()
        assert spec["$schema"].endswith("/vega-lite/v5.json")
        assert spec["width"] == 320
        assert spec["height"] == 200
        # Caption is mapped to Vega-Lite title
        assert spec.get("title", {}).get("text") == "Test chart caption"

    @pytest.mark.skipif(not HAS_VL_CONVERT, reason="vl-convert-python (vl_convert) is not available")
    async def test_export_svg(self, auth_client: AsyncClient, test_report_id: str, test_section_id: str):
        block_id = await self._create_chart_block(
            auth_client,
            report_id=test_report_id,
            section_id=test_section_id,
        )

        resp = await auth_client.get(
            f"/api/v1/blocks/{block_id}/chart/export",
            params={"format": "svg", "width": 320, "height": 200, "locale": "ru"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("image/svg+xml")
        body = resp.content.decode("utf-8", errors="replace")
        assert "<svg" in body.lower()

    @pytest.mark.skipif(not HAS_VL_CONVERT, reason="vl-convert-python (vl_convert) is not available")
    async def test_export_png(self, auth_client: AsyncClient, test_report_id: str, test_section_id: str):
        block_id = await self._create_chart_block(
            auth_client,
            report_id=test_report_id,
            section_id=test_section_id,
        )

        resp = await auth_client.get(
            f"/api/v1/blocks/{block_id}/chart/export",
            params={"format": "png", "width": 320, "height": 200, "scale": 1.0, "locale": "ru"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("image/png")
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(resp.content) > 1000  # sanity: should not be empty/tiny

    @pytest.mark.skipif(not HAS_VL_CONVERT, reason="vl-convert-python (vl_convert) is not available")
    async def test_export_pdf(self, auth_client: AsyncClient, test_report_id: str, test_section_id: str):
        block_id = await self._create_chart_block(
            auth_client,
            report_id=test_report_id,
            section_id=test_section_id,
        )

        resp = await auth_client.get(
            f"/api/v1/blocks/{block_id}/chart/export",
            params={"format": "pdf", "width": 320, "height": 200, "locale": "ru"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF")
        assert len(resp.content) > 1000

    async def test_chart_export_rejects_non_chart_block(
        self, auth_client: AsyncClient, test_report_id: str, test_section_id: str
    ):
        text_block_id = await self._create_text_block(
            auth_client,
            report_id=test_report_id,
            section_id=test_section_id,
        )

        resp = await auth_client.get(f"/api/v1/blocks/{text_block_id}/chart/vega-spec")
        assert resp.status_code == 400

    async def test_chart_export_not_found(self, auth_client: AsyncClient):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.get(f"/api/v1/blocks/{fake_id}/chart/vega-spec")
        assert resp.status_code == 404




