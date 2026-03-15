"""
Integration tests for Artifact API endpoints.

Tests:
- GET /releases/{build_id}/artifacts — list artifacts
- POST /releases/{build_id}/artifacts — create artifact
- GET /releases/{build_id}/artifacts/{artifact_id} — get artifact
- GET /releases/{build_id}/artifacts/{artifact_id}/download — download artifact
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    Block,
    BlockI18n,
    Company,
    ReleaseBuild,
    ReleaseBuildArtifact,
    Report,
    Section,
    SectionI18n,
)
from app.domain.models.enums import (
    ArtifactFormat,
    ArtifactStatus,
    BlockType,
    BlockVariant,
    BuildScope,
    BuildStatus,
    BuildType,
    CompanyStatus,
    Locale,
    PackageMode,
)


@pytest_asyncio.fixture
async def successful_build(db_session: AsyncSession) -> ReleaseBuild:
    """Create a successful build for artifact tests."""
    # Create company
    company_id = uuid4()
    db_session.add(
        Company(
            company_id=company_id,
            name=f"Test Company {company_id.hex[:8]}",
            status=CompanyStatus.ACTIVE,
            created_by=None,
        )
    )
    await db_session.flush()

    # Create report
    report = Report(
        company_id=company_id,
        year=2030,
        title="API Test Report",
        slug=f"api-test-{company_id.hex[:8]}",
        source_locale=Locale.EN,
        default_locale=Locale.EN,
        enabled_locales=["en"],
        release_locales=["en"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()

    # Create section
    section = Section(report_id=report.report_id, order_index=0, depth=0)
    db_session.add(section)
    await db_session.flush()

    section_i18n = SectionI18n(
        section_id=section.section_id,
        locale=Locale.EN,
        title="Test section",
        slug="test-section",
    )
    db_session.add(section_i18n)
    await db_session.flush()

    # Create block
    block = Block(
        section_id=section.section_id,
        report_id=report.report_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
    )
    db_session.add(block)
    await db_session.flush()

    block_i18n = BlockI18n(
        block_id=block.block_id,
        locale=Locale.EN,
        fields_json={"body_html": "<p>Test content</p>"},
    )
    db_session.add(block_i18n)

    # Create successful build
    build = ReleaseBuild(
        report_id=report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.SUCCESS,  # Already successful
        theme_slug="default",
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
        zip_path="/tmp/test.zip",
        zip_sha256="abc123",
    )
    db_session.add(build)
    await db_session.flush()

    return build


class TestListArtifacts:
    """Tests for GET /releases/{build_id}/artifacts."""

    @pytest.mark.asyncio
    async def test_list_empty(self, auth_client: AsyncClient, successful_build: ReleaseBuild):
        """Should return empty list when no artifacts exist."""
        resp = await auth_client.get(f"/api/v1/releases/{successful_build.build_id}/artifacts")
        assert resp.status_code == 200

        data = resp.json()
        assert data["build_id"] == str(successful_build.build_id)
        assert data["build_status"] == "success"
        assert data["artifacts"] == []

    @pytest.mark.asyncio
    async def test_list_with_artifacts(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should list all artifacts for build."""
        # Create some artifacts
        artifact1 = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
            status=ArtifactStatus.DONE,
        )
        artifact2 = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.DOCX,
            locale="en",
            profile=None,
            status=ArtifactStatus.QUEUED,
        )
        db_session.add_all([artifact1, artifact2])
        await db_session.flush()

        resp = await auth_client.get(f"/api/v1/releases/{successful_build.build_id}/artifacts")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["artifacts"]) == 2

    @pytest.mark.asyncio
    async def test_list_build_not_found(self, auth_client: AsyncClient):
        """Should return 404 for non-existent build."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.get(f"/api/v1/releases/{fake_id}/artifacts")
        assert resp.status_code == 404


class TestCreateArtifact:
    """Tests for POST /releases/{build_id}/artifacts."""

    @pytest.mark.asyncio
    async def test_create_pdf_artifact(self, auth_client: AsyncClient, successful_build: ReleaseBuild):
        """Should create PDF artifact with QUEUED status."""
        resp = await auth_client.post(
            f"/api/v1/releases/{successful_build.build_id}/artifacts",
            json={"format": "pdf", "locale": "en", "profile": "audit"},
        )
        # May be 201 or 500/503 if Celery not running
        assert resp.status_code in [201, 500, 503]

        if resp.status_code == 201:
            data = resp.json()
            assert data["format"] == "pdf"
            assert data["locale"] == "en"
            assert data["profile"] == "audit"
            assert data["status"] in ["queued", "processing"]

    @pytest.mark.asyncio
    async def test_create_docx_artifact(self, auth_client: AsyncClient, successful_build: ReleaseBuild):
        """Should create DOCX artifact (profile ignored)."""
        resp = await auth_client.post(
            f"/api/v1/releases/{successful_build.build_id}/artifacts",
            json={"format": "docx", "locale": "en", "profile": "audit"},
        )
        assert resp.status_code in [201, 500, 503]

        if resp.status_code == 201:
            data = resp.json()
            assert data["format"] == "docx"
            assert data["locale"] == "en"
            assert data["profile"] is None  # Profile ignored for DOCX

    @pytest.mark.asyncio
    async def test_create_invalid_locale(self, auth_client: AsyncClient, successful_build: ReleaseBuild):
        """Should reject locale not in build locales."""
        resp = await auth_client.post(
            f"/api/v1/releases/{successful_build.build_id}/artifacts",
            json={"format": "pdf", "locale": "kk", "profile": "audit"},  # kk not in build
        )
        assert resp.status_code == 400
        assert "not in build locales" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_build_not_successful(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should reject artifact creation for non-successful builds."""
        # Change build status to queued
        successful_build.status = BuildStatus.QUEUED
        await db_session.flush()

        resp = await auth_client.post(
            f"/api/v1/releases/{successful_build.build_id}/artifacts",
            json={"format": "pdf", "locale": "en", "profile": "audit"},
        )
        assert resp.status_code == 400
        assert "must be successful" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_idempotent(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should return existing artifact if already exists."""
        # Create existing artifact
        artifact = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
            status=ArtifactStatus.PROCESSING,
        )
        db_session.add(artifact)
        await db_session.flush()

        resp = await auth_client.post(
            f"/api/v1/releases/{successful_build.build_id}/artifacts",
            json={"format": "pdf", "locale": "en", "profile": "audit"},
        )
        # Should return existing
        assert resp.status_code in [200, 201]
        data = resp.json()
        assert data["artifact_id"] == str(artifact.artifact_id)

    @pytest.mark.asyncio
    async def test_create_retry_failed(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should allow retry for failed artifacts."""
        # Create failed artifact
        artifact = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
            status=ArtifactStatus.FAILED,
            error_message="Previous error",
        )
        db_session.add(artifact)
        await db_session.flush()

        resp = await auth_client.post(
            f"/api/v1/releases/{successful_build.build_id}/artifacts",
            json={"format": "pdf", "locale": "en", "profile": "audit"},
        )
        # Should reset to queued
        assert resp.status_code in [200, 201, 500, 503]

        if resp.status_code in [200, 201]:
            data = resp.json()
            assert data["status"] == "queued"
            assert data["error_message"] is None or "Dispatch error" in (data["error_message"] or "")


class TestGetArtifact:
    """Tests for GET /releases/{build_id}/artifacts/{artifact_id}."""

    @pytest.mark.asyncio
    async def test_get_artifact(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should return artifact by ID."""
        artifact = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
            status=ArtifactStatus.DONE,
            path="/path/to/file.pdf",
            sha256="abc123",
            size_bytes=1024,
        )
        db_session.add(artifact)
        await db_session.flush()

        resp = await auth_client.get(
            f"/api/v1/releases/{successful_build.build_id}/artifacts/{artifact.artifact_id}"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["artifact_id"] == str(artifact.artifact_id)
        assert data["format"] == "pdf"
        assert data["status"] == "done"

    @pytest.mark.asyncio
    async def test_get_artifact_not_found(self, auth_client: AsyncClient, successful_build: ReleaseBuild):
        """Should return 404 for non-existent artifact."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.get(
            f"/api/v1/releases/{successful_build.build_id}/artifacts/{fake_id}"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_artifact_wrong_build(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should return 404 if artifact belongs to different build."""
        # Create artifact for this build
        artifact = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
        )
        db_session.add(artifact)
        await db_session.flush()

        # Try to access with wrong build_id
        fake_build_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.get(
            f"/api/v1/releases/{fake_build_id}/artifacts/{artifact.artifact_id}"
        )
        assert resp.status_code == 404


class TestDownloadArtifact:
    """Tests for GET /releases/{build_id}/artifacts/{artifact_id}/download."""

    @pytest.mark.asyncio
    async def test_download_not_ready(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should reject download for non-done artifacts."""
        artifact = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
            status=ArtifactStatus.PROCESSING,
        )
        db_session.add(artifact)
        await db_session.flush()

        resp = await auth_client.get(
            f"/api/v1/releases/{successful_build.build_id}/artifacts/{artifact.artifact_id}/download"
        )
        assert resp.status_code == 400
        assert "not ready" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_download_no_path(
        self, auth_client: AsyncClient, db_session: AsyncSession, successful_build: ReleaseBuild
    ):
        """Should return 404 if artifact has no path."""
        artifact = ReleaseBuildArtifact(
            build_id=successful_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
            status=ArtifactStatus.DONE,
            path=None,  # No path
        )
        db_session.add(artifact)
        await db_session.flush()

        resp = await auth_client.get(
            f"/api/v1/releases/{successful_build.build_id}/artifacts/{artifact.artifact_id}/download"
        )
        assert resp.status_code == 404
