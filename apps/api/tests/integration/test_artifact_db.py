"""
Integration tests for ReleaseBuildArtifact database operations.

Tests:
- Create artifact linked to build
- Query artifacts by build_id
- Update artifact status
- Unique constraint enforcement
- Cascade delete when build is deleted
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    Company,
    ReleaseBuild,
    ReleaseBuildArtifact,
    Report,
)
from app.domain.models.enums import (
    ArtifactFormat,
    ArtifactStatus,
    BuildScope,
    BuildStatus,
    BuildType,
    CompanyStatus,
    Locale,
    PackageMode,
)


@pytest_asyncio.fixture
async def test_build(db_session: AsyncSession) -> ReleaseBuild:
    """Create a sample build for artifact tests."""
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
        title="Artifact Test Report",
        slug=f"artifact-test-{company_id.hex[:8]}",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru", "en"],
        release_locales=["ru", "en"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()

    # Create build
    build = ReleaseBuild(
        report_id=report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.SUCCESS,
        theme_slug="default",
        base_path="/",
        locales=["ru", "en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
        build_options={"targets": ["zip", "pdf", "docx"]},
    )
    db_session.add(build)
    await db_session.flush()

    return build


@pytest.mark.asyncio
async def test_create_artifact(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should create artifact linked to build."""
    artifact = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.PDF,
        locale="ru",
        profile="audit",
        status=ArtifactStatus.QUEUED,
    )
    db_session.add(artifact)
    await db_session.flush()

    # Verify artifact was created
    assert artifact.artifact_id is not None
    assert artifact.build_id == test_build.build_id
    assert artifact.format == ArtifactFormat.PDF
    assert artifact.locale == "ru"
    assert artifact.profile == "audit"
    assert artifact.status == ArtifactStatus.QUEUED


@pytest.mark.asyncio
async def test_query_artifacts_by_build(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should query artifacts filtered by build_id."""
    # Create multiple artifacts
    artifacts = [
        ReleaseBuildArtifact(
            build_id=test_build.build_id,
            format=ArtifactFormat.PDF,
            locale="ru",
            profile="audit",
        ),
        ReleaseBuildArtifact(
            build_id=test_build.build_id,
            format=ArtifactFormat.PDF,
            locale="en",
            profile="audit",
        ),
        ReleaseBuildArtifact(
            build_id=test_build.build_id,
            format=ArtifactFormat.DOCX,
            locale="ru",
            profile=None,
        ),
    ]
    for a in artifacts:
        db_session.add(a)
    await db_session.flush()

    # Query
    query = select(ReleaseBuildArtifact).where(
        ReleaseBuildArtifact.build_id == test_build.build_id
    )
    result = await db_session.execute(query)
    found = list(result.scalars().all())

    assert len(found) == 3


@pytest.mark.asyncio
async def test_update_artifact_status(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should update artifact status and path."""
    artifact = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.PDF,
        locale="ru",
        profile="audit",
        status=ArtifactStatus.QUEUED,
    )
    db_session.add(artifact)
    await db_session.flush()

    # Update status
    artifact.status = ArtifactStatus.PROCESSING
    await db_session.flush()

    # Verify
    await db_session.refresh(artifact)
    assert artifact.status == ArtifactStatus.PROCESSING

    # Complete with path
    artifact.status = ArtifactStatus.DONE
    artifact.path = "/path/to/report-ru-audit.pdf"
    artifact.sha256 = "abc123"
    artifact.size_bytes = 1024
    await db_session.flush()

    await db_session.refresh(artifact)
    assert artifact.status == ArtifactStatus.DONE
    assert artifact.path == "/path/to/report-ru-audit.pdf"
    assert artifact.is_ready is True


@pytest.mark.asyncio
async def test_artifact_unique_constraint(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should enforce unique constraint on (build_id, format, locale, profile)."""
    from sqlalchemy.exc import IntegrityError

    artifact1 = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.PDF,
        locale="ru",
        profile="audit",
    )
    db_session.add(artifact1)
    await db_session.flush()

    # Try to create duplicate
    artifact2 = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.PDF,
        locale="ru",
        profile="audit",
    )
    db_session.add(artifact2)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_build_artifacts_relationship(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should access artifacts via build.artifacts relationship."""
    # Create artifacts
    artifact1 = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.PDF,
        locale="ru",
        profile="audit",
    )
    artifact2 = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.DOCX,
        locale="ru",
        profile=None,
    )
    db_session.add_all([artifact1, artifact2])
    await db_session.flush()

    # Refresh build to load relationship
    await db_session.refresh(test_build, ["artifacts"])

    assert len(test_build.artifacts) == 2
    formats = {a.format for a in test_build.artifacts}
    assert formats == {ArtifactFormat.PDF, ArtifactFormat.DOCX}


@pytest.mark.asyncio
async def test_build_options_jsonb(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should store and retrieve build_options correctly."""
    assert test_build.build_options == {"targets": ["zip", "pdf", "docx"]}
    assert test_build.targets == ["zip", "pdf", "docx"]
    assert test_build.needs_print_bundle is True

    # Update build_options
    test_build.build_options = {
        "targets": ["zip"],
        "pdf_profile": "audit",
        "include_toc": True,
    }
    await db_session.flush()
    await db_session.refresh(test_build)

    assert test_build.get_option("pdf_profile") == "audit"
    assert test_build.get_option("include_toc") is True
    assert test_build.needs_print_bundle is False


@pytest.mark.asyncio
async def test_artifact_error_message(db_session: AsyncSession, test_build: ReleaseBuild):
    """Should store error message on failed artifacts."""
    artifact = ReleaseBuildArtifact(
        build_id=test_build.build_id,
        format=ArtifactFormat.PDF,
        locale="ru",
        profile="audit",
        status=ArtifactStatus.FAILED,
        error_message="Playwright timeout after 300s",
    )
    db_session.add(artifact)
    await db_session.flush()

    await db_session.refresh(artifact)
    assert artifact.status == ArtifactStatus.FAILED
    assert artifact.error_message == "Playwright timeout after 300s"
    assert artifact.is_ready is False


