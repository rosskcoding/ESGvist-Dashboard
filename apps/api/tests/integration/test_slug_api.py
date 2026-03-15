"""
Integration tests for slug-based API endpoints.
"""

import pytest
from httpx import AsyncClient

from app.domain.models.enums import Locale


class TestReportSlugAPI:
    """Tests for report slug-based endpoints."""

    @pytest.mark.asyncio
    async def test_create_report_auto_generates_slug(
        self,
        auth_client: AsyncClient,
    ):
        """Creating a report without slug auto-generates one."""
        response = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2024,
                "title": "Annual Report",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "slug" in data
        assert data["slug"] == "2024-annual-report"

    @pytest.mark.asyncio
    async def test_create_report_with_custom_slug(
        self,
        auth_client: AsyncClient,
    ):
        """Creating a report with custom slug uses provided value."""
        response = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2024,
                "title": "Custom Title",
                "slug": "my-custom-slug",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "my-custom-slug"

    @pytest.mark.asyncio
    async def test_get_report_by_slug(
        self,
        auth_client: AsyncClient,
    ):
        """Getting a report by slug returns correct report."""
        # Create report first
        create_response = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2025,
                "title": "Test Report",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        assert create_response.status_code == 201
        created_report = create_response.json()
        slug = created_report["slug"]

        # Get by slug
        response = await auth_client.get(f"/api/v1/reports/by-slug/{slug}")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == slug
        assert data["report_id"] == created_report["report_id"]

    @pytest.mark.asyncio
    async def test_get_report_by_slug_not_found(
        self,
        auth_client: AsyncClient,
    ):
        """Getting a non-existent slug returns 404."""
        response = await auth_client.get("/api/v1/reports/by-slug/non-existent-slug")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_report_slug(
        self,
        auth_client: AsyncClient,
    ):
        """Updating report slug works."""
        # Create report
        create_response = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2024,
                "title": "Original",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        report_id = create_response.json()["report_id"]

        # Update slug
        response = await auth_client.patch(
            f"/api/v1/reports/{report_id}",
            json={"slug": "new-custom-slug"},
        )
        assert response.status_code == 200
        assert response.json()["slug"] == "new-custom-slug"

    @pytest.mark.asyncio
    async def test_update_report_slug_conflict(
        self,
        auth_client: AsyncClient,
    ):
        """Updating slug to existing value returns 422."""
        # Create two reports
        await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2024,
                "title": "First",
                "slug": "first-report",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        second = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2024,
                "title": "Second",
                "slug": "second-report",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        report_id = second.json()["report_id"]

        # Try to update second report's slug to first's
        response = await auth_client.patch(
            f"/api/v1/reports/{report_id}",
            json={"slug": "first-report"},
        )
        assert response.status_code == 422
        assert "already in use" in response.json()["detail"].lower()


class TestSectionSlugAPI:
    """Tests for section slug-based endpoints."""

    @pytest.mark.asyncio
    async def test_get_section_by_slug(
        self,
        auth_client: AsyncClient,
    ):
        """Getting a section by report slug and section slug works."""
        # Create report
        report_response = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2025,
                "title": "Test",
                "slug": "test-report",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        report_id = report_response.json()["report_id"]

        # Create section
        section_response = await auth_client.post(
            "/api/v1/sections",
            json={
                "report_id": report_id,
                "order_index": 0,
                "i18n": [
                    {
                        "locale": "en",
                        "title": "First section",
                        "slug": "first-section",
                    }
                ],
            },
        )
        assert section_response.status_code == 201
        section_id = section_response.json()["section_id"]

        # Get by slug
        response = await auth_client.get(
            "/api/v1/sections/by-slug/test-report/first-section"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["section_id"] == section_id

    @pytest.mark.asyncio
    async def test_get_section_by_slug_report_not_found(
        self,
        auth_client: AsyncClient,
    ):
        """Getting section with non-existent report slug returns 404."""
        response = await auth_client.get(
            "/api/v1/sections/by-slug/non-existent/some-section"
        )
        assert response.status_code == 404
        assert "report" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_section_by_slug_section_not_found(
        self,
        auth_client: AsyncClient,
    ):
        """Getting non-existent section slug returns 404."""
        # Create report
        report_response = await auth_client.post(
            "/api/v1/reports",
            json={
                "year": 2025,
                "title": "Empty",
                "slug": "empty-report",
                "source_locale": "en",
                "default_locale": "en",
                "enabled_locales": ["en"],
            },
        )
        assert report_response.status_code == 201

        # Try to get non-existent section
        response = await auth_client.get(
            "/api/v1/sections/by-slug/empty-report/non-existent"
        )
        assert response.status_code == 404
        assert "section" in response.json()["detail"].lower()
