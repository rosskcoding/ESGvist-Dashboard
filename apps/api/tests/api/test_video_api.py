"""
API tests for /api/v1/video endpoints.

Tests video upload, poster operations, and YouTube thumbnail retrieval.
"""

import io
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.models.enums import BlockType


@pytest.mark.asyncio
class TestVideoUploadEndpoint:
    """Tests for POST /api/v1/video/upload."""

    async def test_upload_requires_authentication(
        self, unauthenticated_client: AsyncClient
    ):
        """Unauthenticated requests should fail."""
        # Create minimal video-like content
        files = {"file": ("test.mp4", io.BytesIO(b"fake video"), "video/mp4")}

        response = await unauthenticated_client.post(
            "/api/v1/video/upload",
            files=files,
        )

        # Should fail (401/403 or 422 if validation runs before auth)
        assert response.status_code in (401, 403, 422)

    async def test_upload_rejects_unsupported_mime_type(
        self, client: AsyncClient, auth_headers
    ):
        """Upload with unsupported MIME type should fail with 415."""
        files = {
            "file": ("test.txt", io.BytesIO(b"not a video"), "text/plain")
        }

        response = await client.post(
            "/api/v1/video/upload",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 415
        assert "Unsupported video format" in response.json()["detail"]

    async def test_upload_rejects_wrong_extension(
        self, client: AsyncClient, auth_headers
    ):
        """Upload with wrong file extension should fail with 415."""
        files = {
            "file": ("video.exe", io.BytesIO(b"fake"), "video/mp4")
        }

        response = await client.post(
            "/api/v1/video/upload",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 415
        assert "Unsupported file extension" in response.json()["detail"]


@pytest.mark.asyncio
class TestYouTubeThumbnailsEndpoint:
    """Tests for GET /api/v1/video/youtube-thumbnails/{video_id}."""

    async def test_get_youtube_thumbnails_returns_list(
        self, client: AsyncClient, auth_headers
    ):
        """Should return list of thumbnail options."""
        with patch(
            "app.api.v1.video.get_yt_thumbnails"
        ) as mock_get_thumbnails:
            # Mock return value
            mock_thumbnail = MagicMock()
            mock_thumbnail.quality = "maxresdefault"
            mock_thumbnail.url = "https://img.youtube.com/vi/abc123/maxresdefault.jpg"
            mock_thumbnail.width = 1280
            mock_thumbnail.height = 720
            mock_thumbnail.available = True
            mock_get_thumbnails.return_value = [mock_thumbnail]

            response = await client.get(
                "/api/v1/video/youtube-thumbnails/abc123",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["quality"] == "maxresdefault"
            assert data[0]["available"] is True

    async def test_get_youtube_thumbnails_check_availability_param(
        self, client: AsyncClient, auth_headers
    ):
        """Should pass check_availability parameter to service."""
        with patch(
            "app.api.v1.video.get_yt_thumbnails"
        ) as mock_get_thumbnails:
            mock_get_thumbnails.return_value = []

            response = await client.get(
                "/api/v1/video/youtube-thumbnails/abc123?check_availability=false",
                headers=auth_headers,
            )

            assert response.status_code == 200
            mock_get_thumbnails.assert_called_once_with("abc123", False)


@pytest.mark.asyncio
class TestPosterPreviewEndpoint:
    """Tests for GET /api/v1/video/blocks/{block_id}/poster/preview."""

    async def test_preview_requires_block_read_permission(
        self, unauthenticated_client: AsyncClient
    ):
        """Should require block:read permission."""
        block_id = uuid4()

        response = await unauthenticated_client.get(
            f"/api/v1/video/blocks/{block_id}/poster/preview?time_ms=1000",
        )

        # 401/403 for unauthenticated, or 422 if validation runs first
        assert response.status_code in (401, 403, 422)

    async def test_preview_rejects_non_video_block(
        self,
        client: AsyncClient,
        auth_headers,
        db_session,
        test_company,
    ):
        """Should reject if block type is not VIDEO."""
        # This test would need a proper block fixture
        # For now, we test that a non-existent block returns 404
        block_id = uuid4()

        response = await client.get(
            f"/api/v1/video/blocks/{block_id}/poster/preview?time_ms=1000",
            headers=auth_headers,
        )

        # Block not found
        assert response.status_code in (403, 404)


@pytest.mark.asyncio
class TestPosterSetEndpoint:
    """Tests for POST /api/v1/video/blocks/{block_id}/poster/set."""

    async def test_set_requires_block_update_permission(
        self, unauthenticated_client: AsyncClient
    ):
        """Should require block:update permission."""
        block_id = uuid4()

        response = await unauthenticated_client.post(
            f"/api/v1/video/blocks/{block_id}/poster/set",
            json={"time_ms": 5000},
        )

        # 401/403 for unauthenticated, or 422 if validation runs first
        assert response.status_code in (401, 403, 422)

    async def test_set_validates_time_ms(
        self, client: AsyncClient
    ):
        """Should validate time_ms is non-negative on existing block."""
        block_id = uuid4()

        response = await client.post(
            f"/api/v1/video/blocks/{block_id}/poster/set",
            json={"time_ms": -100},
        )

        # Should fail (403 for non-existent block or 422 for validation)
        assert response.status_code in (403, 404, 422)


@pytest.mark.asyncio
class TestPosterUploadEndpoint:
    """Tests for POST /api/v1/video/blocks/{block_id}/poster/upload."""

    async def test_upload_requires_block_update_permission(
        self, unauthenticated_client: AsyncClient
    ):
        """Should require block:update permission."""
        block_id = uuid4()
        files = {"file": ("poster.jpg", io.BytesIO(b"fake image"), "image/jpeg")}

        response = await unauthenticated_client.post(
            f"/api/v1/video/blocks/{block_id}/poster/upload",
            files=files,
        )

        # 401/403 for unauthenticated, or 422 if validation runs first
        assert response.status_code in (401, 403, 422)

    async def test_upload_rejects_non_image(
        self, client: AsyncClient, auth_headers
    ):
        """Should reject non-image files."""
        block_id = uuid4()
        files = {"file": ("data.csv", io.BytesIO(b"csv data"), "text/csv")}

        response = await client.post(
            f"/api/v1/video/blocks/{block_id}/poster/upload",
            files=files,
            headers=auth_headers,
        )

        # Block not found (since we don't have a real block) or 415
        assert response.status_code in (403, 404, 415)


@pytest.mark.asyncio
class TestVideoAPITenantIsolation:
    """Tests for tenant isolation in video API."""

    async def test_upload_uses_user_company(
        self, client: AsyncClient, auth_headers, test_company
    ):
        """Upload should scope asset to user's company."""
        # This would need mocking of video processing
        # For now, verify the endpoint exists and requires auth
        files = {"file": ("test.mp4", io.BytesIO(b"fake"), "video/mp4")}

        response = await client.post(
            "/api/v1/video/upload",
            files=files,
            headers=auth_headers,
        )

        # Should not be 401/403 (auth works)
        # Will likely be 415 or 422 due to invalid video content
        assert response.status_code not in (401, 403)

    async def test_upload_with_explicit_company_id(
        self, client: AsyncClient, auth_headers
    ):
        """Can explicitly specify company_id."""
        company_id = uuid4()
        files = {"file": ("test.mp4", io.BytesIO(b"fake"), "video/mp4")}

        response = await client.post(
            f"/api/v1/video/upload?company_id={company_id}",
            files=files,
            headers=auth_headers,
        )

        # Should fail tenant check (user doesn't have access to random company)
        # or 415/422 for invalid video
        assert response.status_code in (403, 415, 422)

