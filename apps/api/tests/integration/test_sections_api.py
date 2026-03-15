"""
Integration tests for Section API endpoints.

Tests for:
- Section CRUD with structure fields
- Bulk reorder endpoint
- Validation and error handling
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient


# Note: These tests require a running test database.
# They use pytest-asyncio and the test fixtures from conftest.py


class TestSectionStructureAPI:
    """Integration tests for section structure fields."""

    @pytest.mark.asyncio
    async def test_create_section_with_structure_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
    ):
        """Create section with depth, label_prefix, label_suffix."""
        response = await client.post(
            "/api/v1/sections",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "depth": 0,
                "label_prefix": "1",
                "label_suffix": None,
                "i18n": [{
                    "locale": "en",
                    "title": "Company Profile",
                    "slug": "company-profile",
                }],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["depth"] == 0
        assert data["label_prefix"] == "1"
        assert data["label_suffix"] is None

    @pytest.mark.asyncio
    async def test_create_section_depth_validation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
    ):
        """Create section with invalid depth (>3) should fail."""
        response = await client.post(
            "/api/v1/sections",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "depth": 4,  # Invalid
                "i18n": [{
                    "locale": "en",
                    "title": "Test",
                    "slug": "test",
                }],
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_section_structure_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_section_id: str,
    ):
        """Update section label_prefix and label_suffix."""
        response = await client.patch(
            f"/api/v1/sections/{test_section_id}",
            headers=auth_headers,
            json={
                "label_prefix": "09",
                "label_suffix": "(p. 10)",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["label_prefix"] == "09"
        assert data["label_suffix"] == "(p. 10)"

    @pytest.mark.asyncio
    async def test_get_sections_returns_structure_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
    ):
        """GET /sections should return structure fields."""
        response = await client.get(
            "/api/v1/sections",
            headers=auth_headers,
            params={"report_id": test_report_id},
        )
        assert response.status_code == 200
        data = response.json()

        if data["items"]:
            section = data["items"][0]
            assert "depth" in section
            assert "label_prefix" in section
            assert "label_suffix" in section


class TestBulkReorderAPI:
    """Integration tests for bulk reorder endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_reorder_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
        test_sections: list[dict],  # Fixture creates 3 sections
    ):
        """Bulk reorder should update order_index of multiple sections."""
        # Reverse the order
        items = [
            {
                "section_id": test_sections[2]["section_id"],
                "order_index": 0,
                "parent_section_id": None,
                "depth": 0,
            },
            {
                "section_id": test_sections[1]["section_id"],
                "order_index": 1,
                "parent_section_id": None,
                "depth": 0,
            },
            {
                "section_id": test_sections[0]["section_id"],
                "order_index": 2,
                "parent_section_id": None,
                "depth": 0,
            },
        ]

        response = await client.post(
            "/api/v1/sections/bulk-reorder",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "items": items,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Verify order is updated
        orders = {s["section_id"]: s["order_index"] for s in data}
        assert orders[test_sections[2]["section_id"]] == 0
        assert orders[test_sections[1]["section_id"]] == 1
        assert orders[test_sections[0]["section_id"]] == 2

    @pytest.mark.asyncio
    async def test_bulk_reorder_move_to_parent(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
        test_sections: list[dict],
    ):
        """Bulk reorder can move section to different parent."""
        parent_id = test_sections[0]["section_id"]
        child_id = test_sections[1]["section_id"]

        response = await client.post(
            "/api/v1/sections/bulk-reorder",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "items": [
                    {
                        "section_id": child_id,
                        "order_index": 0,
                        "parent_section_id": parent_id,
                        "depth": 1,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()

        moved = next(s for s in data if s["section_id"] == child_id)
        assert moved["parent_section_id"] == parent_id
        assert moved["depth"] == 1

    @pytest.mark.asyncio
    async def test_bulk_reorder_self_parent_error(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
        test_section_id: str,
    ):
        """Section cannot be its own parent."""
        response = await client.post(
            "/api/v1/sections/bulk-reorder",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "items": [
                    {
                        "section_id": test_section_id,
                        "order_index": 0,
                        "parent_section_id": test_section_id,  # Self-reference
                        "depth": 1,
                    },
                ],
            },
        )
        assert response.status_code == 422
        assert "cannot be its own parent" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_bulk_reorder_nonexistent_section(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
    ):
        """Reordering non-existent section returns 404."""
        fake_id = str(uuid4())
        response = await client.post(
            "/api/v1/sections/bulk-reorder",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "items": [
                    {
                        "section_id": fake_id,
                        "order_index": 0,
                        "parent_section_id": None,
                        "depth": 0,
                    },
                ],
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_bulk_reorder_empty_items(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_report_id: str,
    ):
        """Empty items list returns validation error."""
        response = await client.post(
            "/api/v1/sections/bulk-reorder",
            headers=auth_headers,
            json={
                "report_id": test_report_id,
                "items": [],
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_reorder_wrong_report(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_section_id: str,
    ):
        """Section from different report returns 404."""
        fake_report_id = str(uuid4())
        response = await client.post(
            "/api/v1/sections/bulk-reorder",
            headers=auth_headers,
            json={
                "report_id": fake_report_id,
                "items": [
                    {
                        "section_id": test_section_id,
                        "order_index": 0,
                        "parent_section_id": None,
                        "depth": 0,
                    },
                ],
            },
        )
        # Either 404 (report not found) or 404 (section not in report)
        assert response.status_code == 404



