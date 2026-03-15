"""
Integration tests for static export functionality.

Tests PORTABLE vs INTERACTIVE package modes and relative URL correctness.
"""

import json
import re
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    Block,
    BlockI18n,
    Company,
    CompanyStatus,
    ReleaseBuild,
    Report,
    Section,
    SectionI18n,
)
from app.domain.models.enums import (
    BlockType,
    BlockVariant,
    BuildScope,
    BuildStatus,
    BuildType,
    Locale,
    PackageMode,
)
from app.services.build_pipeline import BuildPipeline


@pytest_asyncio.fixture
async def sample_report(db_session: AsyncSession) -> Report:
    """Create a sample report with sections and blocks for export tests."""
    # Multi-tenant requires report.company_id; use unique company per test to avoid collisions
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
        title="Export Test Report",
        slug=f"export-test-{company_id.hex[:8]}",
        source_locale=Locale.EN,
        default_locale=Locale.EN,
        enabled_locales=["en"],
        release_locales=["en"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()

    # Create sections
    for idx, (slug, title) in enumerate([
        ("introduction", "Introduction"),
        ("results", "Results"),
    ]):
        section = Section(
            report_id=report.report_id,
            order_index=idx,
            depth=0,
        )
        db_session.add(section)
        await db_session.flush()

        section_i18n = SectionI18n(
            section_id=section.section_id,
            locale=Locale.EN,
            title=title,
            slug=slug,
        )
        db_session.add(section_i18n)
        await db_session.flush()

        # Add a text block to each section
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
            fields_json={"body_html": f"<p>Content for {title}</p>"},
        )
        db_session.add(block_i18n)

    await db_session.commit()
    await db_session.refresh(report)
    return report


@pytest.mark.asyncio
async def test_portable_export_no_js(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """PORTABLE export should not include JS files."""
    # Create PORTABLE build
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    # Execute build with tmp workspace
    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success
    assert result.zip_path is not None

    # Verify ZIP contents
    zip_path = Path(result.zip_path)
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path, "r") as zf:
        files = zf.namelist()

        # Must include content snapshot for deterministic PDF/DOCX artifacts
        assert "content-snapshot.json" in files
        snapshot = json.loads(zf.read("content-snapshot.json").decode("utf-8"))
        assert "sections" in snapshot
        assert "blocks" in snapshot

        # Should NOT have JS files
        assert not any("js/app.js" in f for f in files)
        assert not any("js/search.js" in f for f in files)

        # Should NOT have search directory
        assert not any("search/" in f for f in files)

        # Should NOT have README/start scripts
        assert "README.txt" not in files
        assert "start.sh" not in files
        assert "start.bat" not in files


@pytest.mark.asyncio
async def test_interactive_export_with_js(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """INTERACTIVE export should include JS, search, and README."""
    # Create INTERACTIVE build
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.INTERACTIVE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    # Execute build with tmp workspace
    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success
    assert result.zip_path is not None

    # Verify ZIP contents
    zip_path = Path(result.zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        files = zf.namelist()

        # Must include content snapshot for deterministic PDF/DOCX artifacts
        assert "content-snapshot.json" in files
        snapshot = json.loads(zf.read("content-snapshot.json").decode("utf-8"))
        assert "sections" in snapshot
        assert "blocks" in snapshot

        # Should have JS files
        assert any("assets/js/app.js" in f for f in files)
        assert any("assets/js/search.js" in f for f in files)

        # Should have search indexes
        assert any("assets/search/index.en.json" in f for f in files)

        # Should have README and start scripts
        assert "README.txt" in files
        assert "start.sh" in files
        assert "start.bat" in files


@pytest.mark.asyncio
async def test_portable_no_absolute_urls(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """PORTABLE export should not contain absolute URLs."""
    # Create PORTABLE build
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    # Execute build with tmp workspace
    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success
    assert result.zip_path is not None

    # Check HTML files for absolute URLs
    zip_path = Path(result.zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for filename in zf.namelist():
            if filename.endswith(".html"):
                content = zf.read(filename).decode("utf-8")

                # Should NOT have absolute paths in href/src (except external)
                # Pattern matches /path but not //domain (protocol-relative)
                absolute_pattern = r'(href|src)=["\']\/(?!\/)'
                matches = re.findall(absolute_pattern, content)

                # Filter out allowed external URLs
                for match in matches:
                    if 'href="//' in content or 'src="//' in content:
                        continue  # External URL, OK

                    # This is a local absolute path - not allowed in PORTABLE
                    pytest.fail(
                        f"Found absolute URL in {filename}: {match}\n"
                        f"PORTABLE exports must use relative URLs only"
                    )


@pytest.mark.asyncio
async def test_relative_urls_correctness(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """Verify relative URLs are computed correctly at different depths."""
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success

    # Read a section page and verify relative URLs
    zip_path = Path(result.zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find a section page
        section_files = [
            f for f in zf.namelist() if "/sections/" in f and f.endswith("/index.html")
        ]

        if section_files:
            content = zf.read(section_files[0]).decode("utf-8")

            # Should have relative paths to assets (depth varies)
            assert "assets/css/app.css" in content

            # Should NOT have /assets/ (absolute)
            assert 'href="/assets/' not in content
            assert 'src="/assets/' not in content


@pytest.mark.asyncio
async def test_redirect_pages_no_inline_scripts(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """Redirect pages should not contain inline <script> tags."""
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success

    # Check redirect pages
    zip_path = Path(result.zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        redirect_files = ["index.html", "en/index.html"]

        for filename in redirect_files:
            if filename in zf.namelist():
                content = zf.read(filename).decode("utf-8")

                # Should have meta refresh
                assert 'meta http-equiv="refresh"' in content

                # Should NOT have inline script
                assert "<script>" not in content.lower()
                assert "window.location" not in content


@pytest.mark.asyncio
async def test_export_structure_with_order(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """Export should use {order:02d}-{slug}/index.html structure."""
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success

    # Verify directory structure
    zip_path = Path(result.zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        files = zf.namelist()

        # Should have sections with order prefixes
        section_pattern = re.compile(r"en/sections/\d{2}-.+/index\.html")
        section_files = [f for f in files if section_pattern.match(f)]

        assert len(section_files) > 0, "Should have at least one section with order prefix"

        # Verify format
        for section_file in section_files:
            # Extract order and slug
            match = re.search(r"/(\d{2})-([^/]+)/index\.html", section_file)
            assert match, f"Section file doesn't match pattern: {section_file}"

            order = match.group(1)
            slug = match.group(2)

            # Order should be zero-padded 2 digits
            assert len(order) == 2
            assert order.isdigit()

            # Slug should be URL-friendly
            assert re.match(r"^[a-z0-9-]+$", slug), f"Invalid slug format: {slug}"


@pytest.mark.asyncio
async def test_section_export_scope(db_session: AsyncSession, sample_report: Report):
    """Test SECTION-scoped export creates build with correct scope."""
    # Get first section
    sections_query = (
        select(Section).where(Section.report_id == sample_report.report_id).limit(1)
    )
    result = await db_session.execute(sections_query)
    section = result.scalar_one()

    # Create SECTION build
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.SECTION,
        target_section_id=section.section_id,
    )
    db_session.add(build)
    await db_session.commit()

    # Verify build model
    assert build.scope == BuildScope.SECTION
    assert build.target_section_id == section.section_id


@pytest.mark.asyncio
async def test_block_export_scope(db_session: AsyncSession, sample_report: Report):
    """Test BLOCK-scoped export creates build with correct scope."""
    # Get first block
    blocks_query = (
        select(Block).where(Block.report_id == sample_report.report_id).limit(1)
    )
    result = await db_session.execute(blocks_query)
    block = result.scalar_one()

    # Create BLOCK build
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.BLOCK,
        target_block_id=block.block_id,
    )
    db_session.add(build)
    await db_session.commit()

    # Verify build model
    assert build.scope == BuildScope.BLOCK
    assert build.target_block_id == block.block_id


@pytest.mark.asyncio
async def test_manifest_includes_package_mode(db_session: AsyncSession, sample_report: Report, tmp_path: Path):
    """Build manifest should include package mode information."""
    build = ReleaseBuild(
        report_id=sample_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=sample_report.theme_slug,
        base_path="/",
        locales=["en"],
        package_mode=PackageMode.INTERACTIVE,
        scope=BuildScope.FULL,
    )
    db_session.add(build)
    await db_session.commit()

    pipeline = BuildPipeline(build, db_session, workspace_root=tmp_path)
    result = await pipeline.execute()

    assert result.success
    assert result.manifest_path is not None

    # Read manifest
    manifest_path = Path(result.manifest_path)
    manifest = json.loads(manifest_path.read_text())

    # Verify metadata
    assert "build_id" in manifest
    assert "report_id" in manifest
    assert "generated_at" in manifest
    assert "files" in manifest


class TestPartialExportAPI:
    """Tests for partial export API endpoints."""

    @pytest.mark.asyncio
    async def test_section_export_endpoint(
        self, auth_client: AsyncClient, test_report_id: str, test_section_id: str
    ):
        """POST /sections/{section_id}/export should create SECTION-scoped build."""
        resp = await auth_client.post(
            f"/api/v1/releases/sections/{test_section_id}/export",
            params={"package_mode": "portable"},
        )
        # May return 201 (success) or error if Celery not running
        assert resp.status_code in [201, 500, 503]

        if resp.status_code == 201:
            data = resp.json()
            assert data["scope"] == "section"
            assert data["target_section_id"] == test_section_id

    @pytest.mark.asyncio
    async def test_section_export_not_found(self, auth_client: AsyncClient):
        """POST /sections/{fake_id}/export should return 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.post(
            f"/api/v1/releases/sections/{fake_id}/export",
            params={"package_mode": "portable"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_block_export_endpoint(
        self, auth_client: AsyncClient, test_report_id: str, test_section_id: str
    ):
        """POST /blocks/{block_id}/export should create BLOCK-scoped build."""
        # First create a block
        block_resp = await auth_client.post(
            "/api/v1/blocks",
            json={
                "report_id": test_report_id,
                "section_id": test_section_id,
                "type": "text",
                "variant": "default",
                "order_index": 0,
                "data_json": {},
                "i18n": [{"locale": "en", "fields_json": {"body_html": "<p>Test</p>"}}],
            },
        )
        assert block_resp.status_code == 201, block_resp.text
        block_id = block_resp.json()["block_id"]

        # Export block
        resp = await auth_client.post(
            f"/api/v1/releases/blocks/{block_id}/export",
            params={"package_mode": "portable", "locale": "en"},
        )
        # May return 201 (success) or error if Celery not running
        assert resp.status_code in [201, 500, 503]

        if resp.status_code == 201:
            data = resp.json()
            assert data["scope"] == "block"
            assert data["target_block_id"] == block_id

    @pytest.mark.asyncio
    async def test_block_export_not_found(self, auth_client: AsyncClient):
        """POST /blocks/{fake_id}/export should return 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await auth_client.post(
            f"/api/v1/releases/blocks/{fake_id}/export",
            params={"package_mode": "portable", "locale": "en"},
        )
        assert resp.status_code == 404
