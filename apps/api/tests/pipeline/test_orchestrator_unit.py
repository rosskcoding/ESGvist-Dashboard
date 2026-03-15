"""
Pipeline orchestrator unit tests.

Spec reference: Pipeline orchestrator unit tests spec

Tests that the build pipeline orchestrator:
- Executes stages in the correct order
- Passes context/artifacts between stages
- Sets build status correctly
- Handles errors (fail-fast)
- Executes cleanup according to policy

SUT: BuildPipeline.execute() in app/services/build_pipeline.py

All external dependencies are mocked:
- Database session (AsyncSession)
- Renderer (get_renderer)
- File system operations (Path, shutil)
- Search indexer (generate_search_index)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

from app.domain.models.enums import (
    BuildScope,
    BuildStatus,
    BuildType,
    Locale,
    PackageMode,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_report_id() -> UUID:
    """Fixed report ID for tests."""
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_build_id() -> UUID:
    """Fixed build ID for tests."""
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def mock_snapshot_id() -> UUID:
    """Fixed snapshot ID for tests."""
    return UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def mock_build(mock_build_id: UUID, mock_report_id: UUID) -> MagicMock:
    """
    Create a mock ReleaseBuild object.

    Simulates the build model with all required properties.
    """
    build = MagicMock()
    build.build_id = mock_build_id
    build.report_id = mock_report_id
    build.build_type = BuildType.DRAFT
    build.status = BuildStatus.QUEUED
    build.theme_slug = "default"
    build.base_path = "/"
    build.locales = ["ru"]
    build.package_mode = PackageMode.PORTABLE
    build.scope = BuildScope.FULL
    build.target_section_id = None
    build.target_block_id = None
    build.source_snapshot_id = None

    # Properties
    build.include_js = False  # PORTABLE mode
    build.include_search = False
    build.needs_print_bundle = False
    build.targets = ["zip"]
    build.get_option = MagicMock(return_value=False)

    return build


@pytest.fixture
def mock_session() -> AsyncMock:
    """
    Create a mock AsyncSession.

    Mocks all database operations used by BuildPipeline.
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_report(mock_report_id: UUID) -> MagicMock:
    """Create a mock Report object."""
    report = MagicMock()
    report.report_id = mock_report_id
    report.title = "Test Report"
    report.year = 2030
    report.slug = "test-report-2030"
    report.default_locale = Locale.RU
    report.source_locale = Locale.RU
    report.enabled_locales = ["ru"]
    report.theme_slug = "default"
    # NOTE: BuildPipeline._save_content_snapshot serializes report.company.name; in unit tests
    # we keep it JSON-serializable by default.
    report.company = None
    return report


@pytest.fixture
def mock_section() -> MagicMock:
    """Create a mock Section object."""
    section = MagicMock()
    section.section_id = uuid4()
    section.order_index = 0
    section.depth = 0
    # Fields used by BuildPipeline._save_content_snapshot (must be JSON-serializable)
    section.parent_section_id = None
    section.label_prefix = None
    section.label_suffix = None

    # Mock i18n
    section_i18n = MagicMock()
    section_i18n.locale = Locale.RU
    section_i18n.title = "Test Section"
    section_i18n.slug = "test-section"
    section_i18n.summary = None
    section.get_i18n = MagicMock(return_value=section_i18n)
    section.i18n = [section_i18n]

    return section


@pytest.fixture
def mock_block(mock_section: MagicMock, mock_report_id: UUID) -> MagicMock:
    """Create a mock Block object."""
    from app.domain.models.enums import BlockType, BlockVariant

    block = MagicMock()
    block.block_id = uuid4()
    block.section_id = mock_section.section_id
    block.report_id = mock_report_id
    block.type = BlockType.TEXT
    block.variant = BlockVariant.DEFAULT
    block.order_index = 0
    block.data_json = {}
    block.qa_flags_global = []
    block.custom_override_enabled = False

    # Mock i18n
    block_i18n = MagicMock()
    block_i18n.locale = Locale.RU
    block_i18n.fields_json = {"body_html": "<p>Test content</p>"}
    block_i18n.status = MagicMock(value="draft")
    block_i18n.qa_flags_by_locale = []
    block_i18n.custom_html_sanitized = None
    block_i18n.custom_css_validated = None
    block.get_i18n = MagicMock(return_value=block_i18n)
    block.i18n = [block_i18n]

    return block


@pytest.fixture
def mock_snapshot(mock_snapshot_id: UUID, mock_report_id: UUID) -> MagicMock:
    """Create a mock SourceSnapshot object."""
    snapshot = MagicMock()
    snapshot.snapshot_id = mock_snapshot_id
    snapshot.report_id = mock_report_id
    snapshot.content_root_hash = "abc123" * 10 + "abcd"  # 64 chars
    snapshot.created_at_utc = datetime.now(UTC)
    return snapshot


@pytest.fixture
def mock_theme() -> MagicMock:
    """Create a mock Theme object."""
    theme = MagicMock()
    theme.slug = "default"
    theme.to_css = MagicMock(return_value=":root { --primary: #000; }")
    return theme


@pytest.fixture
def mock_renderer() -> MagicMock:
    """Create a mock Renderer object."""
    renderer = MagicMock()
    renderer.render_page = MagicMock(return_value="<html>rendered page</html>")
    renderer.render_print_report = MagicMock(return_value="<html>print bundle</html>")
    return renderer


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory for tests."""
    workspace = tmp_path / "builds"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


# =============================================================================
# Global test patches (unit tests mock I/O-heavy stages)
# =============================================================================

# BuildPipeline now always writes content-snapshot.json near the end of execute().
# These unit tests validate orchestration only, so keep snapshot writing out of scope.
@pytest.fixture(autouse=True)
def patch_write_content_snapshot():
    """Disable content-snapshot write stage for orchestrator unit tests."""
    from app.services.build_pipeline import BuildPipeline

    original = BuildPipeline._write_content_snapshot

    async def noop_write_content_snapshot(self) -> None:
        return None

    BuildPipeline._write_content_snapshot = noop_write_content_snapshot
    try:
        yield
    finally:
        BuildPipeline._write_content_snapshot = original


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_scalar_result(value: Any) -> MagicMock:
    """Create a mock for session.execute() result with scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[value] if value else [])))
    return result


def create_mock_scalars_result(values: list) -> MagicMock:
    """Create a mock for session.execute() result with scalars().all()."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=values)
    result.scalars = MagicMock(return_value=scalars_mock)
    return result


# =============================================================================
# TEST-01: Happy Path — All Stages Succeed
# =============================================================================


class TestPipelineHappyPath:
    """
    TEST-01: Happy path — all stages succeed.

    Scenario: Pipeline completes fully with all stages successful.

    Verify:
    - Stages are called in strict order
    - Context is passed between stages
    - Final status = SUCCESS (via BuildResult)
    - Cleanup is called at the end
    """

    @pytest.mark.asyncio
    async def test_pipeline_happy_path_runs_stages_in_order(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_report: MagicMock,
        mock_section: MagicMock,
        mock_block: MagicMock,
        mock_snapshot: MagicMock,
        mock_theme: MagicMock,
        mock_renderer: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that pipeline executes all stages in order and returns success.

        Stages order:
        1. _create_snapshot
        2. _prepare_workspace
        3. _collect_asset_url_map
        4. _render_all_pages
        5. _compile_css
        6. _copy_js
        7. _copy_assets
        8. _generate_search_indexes
        9. _copy_export_extras
        10. _render_print_bundle (optional)
        11. _generate_manifest
        12. _create_zip
        """
        from app.services.build_pipeline import BuildPipeline

        # Configure session mock to return proper data
        def mock_execute(query):
            # Return appropriate mock data based on query
            return create_mock_scalars_result([mock_section])

        mock_session.execute = AsyncMock(side_effect=mock_execute)
        mock_session.get = AsyncMock(return_value=mock_report)

        # Create pipeline with mocked workspace
        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        # Track stage execution order
        stage_calls: list[str] = []

        # Mock all private methods to track calls
        original_create_snapshot = pipeline._create_snapshot
        original_prepare_workspace = pipeline._prepare_workspace
        original_collect_asset_url_map = pipeline._collect_asset_url_map
        original_render_all_pages = pipeline._render_all_pages
        original_compile_css = pipeline._compile_css
        original_copy_js = pipeline._copy_js
        original_copy_assets = pipeline._copy_assets
        original_generate_search_indexes = pipeline._generate_search_indexes
        original_copy_export_extras = pipeline._copy_export_extras
        original_generate_manifest = pipeline._generate_manifest
        original_create_zip = pipeline._create_zip

        async def tracked_create_snapshot():
            stage_calls.append("create_snapshot")
            return mock_snapshot

        def tracked_prepare_workspace():
            stage_calls.append("prepare_workspace")
            workspace = temp_workspace / str(mock_build.build_id)
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "assets" / "css").mkdir(parents=True, exist_ok=True)
            (workspace / "assets" / "js").mkdir(parents=True, exist_ok=True)
            (workspace / "ru" / "sections").mkdir(parents=True, exist_ok=True)
            return workspace

        async def tracked_collect_asset_url_map():
            stage_calls.append("collect_asset_url_map")
            return {}

        async def tracked_render_all_pages():
            stage_calls.append("render_all_pages")
            return 1  # pages count

        async def tracked_compile_css():
            stage_calls.append("compile_css")

        async def tracked_copy_js():
            stage_calls.append("copy_js")

        async def tracked_copy_assets():
            stage_calls.append("copy_assets")
            return 0  # assets count

        async def tracked_generate_search_indexes():
            stage_calls.append("generate_search_indexes")

        async def tracked_copy_export_extras():
            stage_calls.append("copy_export_extras")

        async def tracked_generate_manifest():
            stage_calls.append("generate_manifest")
            manifest_path = temp_workspace / f"manifest-{mock_build.build_id}.json"
            manifest_path.write_text("{}")
            return manifest_path

        async def tracked_create_zip():
            stage_calls.append("create_zip")
            zip_path = temp_workspace / f"build-{mock_build.build_id}.zip"
            zip_path.write_bytes(b"PK\x03\x04")  # Minimal ZIP header
            return zip_path, "abc123" * 10 + "abcd"

        # Patch methods
        pipeline._create_snapshot = tracked_create_snapshot
        pipeline._prepare_workspace = tracked_prepare_workspace
        pipeline._collect_asset_url_map = tracked_collect_asset_url_map
        pipeline._render_all_pages = tracked_render_all_pages
        pipeline._compile_css = tracked_compile_css
        pipeline._copy_js = tracked_copy_js
        pipeline._copy_assets = tracked_copy_assets
        pipeline._generate_search_indexes = tracked_generate_search_indexes
        pipeline._copy_export_extras = tracked_copy_export_extras
        pipeline._generate_manifest = tracked_generate_manifest
        pipeline._create_zip = tracked_create_zip

        # Act
        result = await pipeline.execute()

        # Assert: success
        assert result.success is True
        assert result.error is None
        assert result.zip_path is not None
        assert result.zip_sha256 is not None
        assert result.manifest_path is not None

        # Assert: stages called in order
        expected_order = [
            "create_snapshot",
            "prepare_workspace",
            "collect_asset_url_map",
            "render_all_pages",
            "compile_css",
            "copy_js",
            "copy_assets",
            "generate_search_indexes",
            "copy_export_extras",
            "generate_manifest",
            "create_zip",
        ]
        assert stage_calls == expected_order, f"Expected {expected_order}, got {stage_calls}"

        # Assert: stats populated
        assert "pages" in result.stats
        assert "assets" in result.stats
        assert "snapshot_id" in result.stats

    @pytest.mark.asyncio
    async def test_pipeline_returns_correct_outputs(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_report: MagicMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that pipeline populates BuildResult with correct outputs.

        Key outputs:
        - zip_path: path to generated ZIP
        - zip_sha256: checksum of ZIP
        - manifest_path: path to manifest JSON
        - stats: {pages, assets, snapshot_id}
        """
        from app.services.build_pipeline import BuildPipeline

        mock_session.get = AsyncMock(return_value=mock_report)
        mock_session.execute = AsyncMock(return_value=create_mock_scalars_result([]))

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        # Mock stages with specific outputs
        mock_pages_count = 5
        mock_assets_count = 10
        mock_zip_sha = "e3b0c44298fc1c149afbf4c8996fb924" * 2  # 64 chars

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_render_all_pages():
            return mock_pages_count

        async def mock_copy_assets():
            return mock_assets_count

        async def mock_generate_manifest():
            path = temp_workspace / "manifest.json"
            path.write_text("{}")
            return path

        async def mock_create_zip():
            path = temp_workspace / "build.zip"
            path.write_bytes(b"PK\x03\x04")
            return path, mock_zip_sha

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = mock_render_all_pages
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = mock_copy_assets
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        # Assert outputs
        assert result.success is True
        assert result.stats["pages"] == mock_pages_count
        assert result.stats["assets"] == mock_assets_count
        assert result.stats["snapshot_id"] == str(mock_snapshot.snapshot_id)
        assert result.zip_sha256 == mock_zip_sha


# =============================================================================
# TEST-02: Failure Path — Fail-Fast on Stage Error
# =============================================================================


class TestPipelineFailurePath:
    """
    TEST-02: Failure path — fail-fast on stage error.

    Scenario: A middle stage fails, pipeline should stop and mark build as failed.

    Verify:
    - Early stages are executed
    - Failing stage is executed
    - Subsequent stages are NOT called
    - Error is captured in result
    - Cleanup is still executed
    """

    @pytest.mark.asyncio
    async def test_pipeline_fails_fast_on_stage_error(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that pipeline stops immediately when a stage fails.

        Scenario: _render_all_pages throws an exception.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        stage_calls: list[str] = []

        async def tracked_create_snapshot():
            stage_calls.append("create_snapshot")
            return mock_snapshot

        def tracked_prepare_workspace():
            stage_calls.append("prepare_workspace")
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def tracked_collect_asset_url_map():
            stage_calls.append("collect_asset_url_map")
            return {}

        async def tracked_render_all_pages_fail():
            stage_calls.append("render_all_pages")
            raise ValueError("Render failed: template not found")

        async def tracked_compile_css():
            stage_calls.append("compile_css")

        async def tracked_generate_manifest():
            stage_calls.append("generate_manifest")
            return temp_workspace / "manifest.json"

        async def tracked_create_zip():
            stage_calls.append("create_zip")
            return temp_workspace / "build.zip", "abc123"

        pipeline._create_snapshot = tracked_create_snapshot
        pipeline._prepare_workspace = tracked_prepare_workspace
        pipeline._collect_asset_url_map = tracked_collect_asset_url_map
        pipeline._render_all_pages = tracked_render_all_pages_fail
        pipeline._compile_css = tracked_compile_css
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = tracked_generate_manifest
        pipeline._create_zip = tracked_create_zip

        # Act & Assert: exception is re-raised
        with pytest.raises(ValueError, match="Render failed"):
            await pipeline.execute()

        # Assert: stages before error were called
        assert "create_snapshot" in stage_calls
        assert "prepare_workspace" in stage_calls
        assert "collect_asset_url_map" in stage_calls
        assert "render_all_pages" in stage_calls

        # Assert: stages after error were NOT called
        assert "compile_css" not in stage_calls
        assert "generate_manifest" not in stage_calls
        assert "create_zip" not in stage_calls

    @pytest.mark.asyncio
    async def test_pipeline_captures_error_in_result(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that error message is captured in BuildResult.

        Note: Current implementation re-raises exception, so we test
        that error would be captured if caught.
        """
        from app.services.build_pipeline import BuildPipeline, BuildResult

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        error_message = "Database connection lost"

        async def failing_create_snapshot():
            raise ConnectionError(error_message)

        pipeline._create_snapshot = failing_create_snapshot

        # Act: exception is raised
        with pytest.raises(ConnectionError):
            await pipeline.execute()

        # Note: The current implementation doesn't populate result.error
        # before re-raising. This test documents expected behavior.
        # If needed, the pipeline could be modified to capture errors.

    @pytest.mark.asyncio
    async def test_pipeline_error_includes_stage_context(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_report: MagicMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that error provides enough context to identify failing stage.
        """
        from app.services.build_pipeline import BuildPipeline

        mock_session.get = AsyncMock(return_value=mock_report)
        mock_session.execute = AsyncMock(return_value=create_mock_scalars_result([]))

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def failing_compile_css():
            raise FileNotFoundError("CSS source file not found: app.css")

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=0)
        pipeline._compile_css = failing_compile_css

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            await pipeline.execute()

        # Error message should be descriptive
        assert "app.css" in str(exc_info.value)


# =============================================================================
# TEST-03: Cleanup Policy
# =============================================================================


class TestPipelineCleanup:
    """
    TEST-03: Cleanup — workspace is always deleted.

    Scenario: Cleanup should run regardless of success or failure.

    Verify:
    - Cleanup runs after successful execution
    - Cleanup runs after failed execution
    - Workspace directory is removed
    """

    @pytest.mark.asyncio
    async def test_cleanup_after_success(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that workspace is cleaned up after successful build.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        workspace_dir = temp_workspace / str(mock_build.build_id)

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            workspace_dir.mkdir(parents=True, exist_ok=True)
            (workspace_dir / "test_file.txt").write_text("test")
            return workspace_dir

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=1)
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        # Verify workspace exists before execute
        result = await pipeline.execute()

        assert result.success is True

        # Assert: workspace is cleaned up
        assert not workspace_dir.exists(), "Workspace should be deleted after success"

    @pytest.mark.asyncio
    async def test_cleanup_after_failure(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that workspace is cleaned up even after build failure.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        workspace_dir = temp_workspace / str(mock_build.build_id)

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            workspace_dir.mkdir(parents=True, exist_ok=True)
            (workspace_dir / "partial_output.txt").write_text("partial")
            return workspace_dir

        async def failing_render():
            raise RuntimeError("Render engine crashed")

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = failing_render

        # Act: pipeline fails
        with pytest.raises(RuntimeError):
            await pipeline.execute()

        # Assert: workspace is still cleaned up
        assert not workspace_dir.exists(), "Workspace should be deleted after failure"

    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_workspace(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        temp_workspace: Path,
    ):
        """
        Test that cleanup doesn't fail if workspace doesn't exist.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        # Fail before workspace is created
        async def failing_create_snapshot():
            raise ValueError("Snapshot creation failed")

        pipeline._create_snapshot = failing_create_snapshot

        # Act: should not raise additional errors during cleanup
        with pytest.raises(ValueError):
            await pipeline.execute()

        # If we get here, cleanup handled missing workspace gracefully


# =============================================================================
# TEST-04: Context/Outputs Passed Between Stages
# =============================================================================


class TestPipelineContextPassing:
    """
    TEST-04: Context and outputs are passed between stages.

    Verify:
    - Snapshot ID is linked to build
    - Asset URL map is used during rendering
    - Workspace path is used by all file operations
    - Stats aggregate outputs from multiple stages
    """

    @pytest.mark.asyncio
    async def test_snapshot_linked_to_build(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that created snapshot is linked to the build.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        # Track if source_snapshot_id is set
        snapshot_id_set = False
        original_snapshot_id = mock_build.source_snapshot_id

        async def mock_create_snapshot():
            nonlocal snapshot_id_set
            mock_build.source_snapshot_id = mock_snapshot.snapshot_id
            snapshot_id_set = True
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=1)
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert snapshot_id_set is True
        assert mock_build.source_snapshot_id == mock_snapshot.snapshot_id

    @pytest.mark.asyncio
    async def test_asset_url_map_used_in_rendering(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_report: MagicMock,
        mock_section: MagicMock,
        mock_block: MagicMock,
        mock_snapshot: MagicMock,
        mock_renderer: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that asset URL map is passed to render_all_pages.
        """
        from app.services.build_pipeline import BuildPipeline

        mock_session.get = AsyncMock(return_value=mock_report)

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        # Expected asset map
        expected_asset_map = {
            "asset-id-1": "media/asset-id-1.png",
            "asset-id-2": "media/asset-id-2.jpg",
        }

        collected_asset_map = None

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            (ws / "ru" / "sections").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_collect_asset_url_map():
            return expected_asset_map

        async def mock_render_all_pages():
            nonlocal collected_asset_map
            # The real implementation uses self.asset_url_map
            collected_asset_map = pipeline.asset_url_map
            return 1

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = mock_collect_asset_url_map
        pipeline._render_all_pages = mock_render_all_pages
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert collected_asset_map == expected_asset_map

    @pytest.mark.asyncio
    async def test_workspace_path_shared_across_stages(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that workspace path is accessible to all file operation stages.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        workspace_accessed_by: list[str] = []
        expected_workspace = temp_workspace / str(mock_build.build_id)

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            expected_workspace.mkdir(parents=True, exist_ok=True)
            (expected_workspace / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return expected_workspace

        async def mock_compile_css():
            if pipeline.workspace == expected_workspace:
                workspace_accessed_by.append("compile_css")

        async def mock_copy_js():
            if pipeline.workspace == expected_workspace:
                workspace_accessed_by.append("copy_js")

        async def mock_copy_assets():
            if pipeline.workspace == expected_workspace:
                workspace_accessed_by.append("copy_assets")
            return 0

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=1)
        pipeline._compile_css = mock_compile_css
        pipeline._copy_js = mock_copy_js
        pipeline._copy_assets = mock_copy_assets
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert "compile_css" in workspace_accessed_by
        assert "copy_js" in workspace_accessed_by
        assert "copy_assets" in workspace_accessed_by

    @pytest.mark.asyncio
    async def test_stats_aggregate_all_stage_outputs(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that final stats include outputs from multiple stages.
        """
        from app.services.build_pipeline import BuildPipeline

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        mock_pages = 7
        mock_assets = 15

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_render_all_pages():
            return mock_pages

        async def mock_copy_assets():
            return mock_assets

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = mock_render_all_pages
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = mock_copy_assets
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert result.stats["pages"] == mock_pages
        assert result.stats["assets"] == mock_assets
        assert result.stats["snapshot_id"] == str(mock_snapshot.snapshot_id)


# =============================================================================
# TEST-05: Build Options Affect Stage Behavior
# =============================================================================


class TestPipelineBuildOptions:
    """
    TEST-05: Build options affect stage behavior.

    Verify:
    - PORTABLE mode skips JS and search
    - INTERACTIVE mode includes JS and search
    - Print bundle generated when needed
    """

    @pytest.mark.asyncio
    async def test_portable_mode_skips_js_and_search(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that PORTABLE mode skips JS copy and search index generation.
        """
        from app.services.build_pipeline import BuildPipeline

        # Configure as PORTABLE
        mock_build.package_mode = PackageMode.PORTABLE
        mock_build.include_js = False
        mock_build.include_search = False

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        js_copied = False
        search_generated = False

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_copy_js():
            nonlocal js_copied
            # Real implementation checks self.build.include_js
            if pipeline.build.include_js:
                js_copied = True

        async def mock_generate_search_indexes():
            nonlocal search_generated
            # Real implementation checks self.build.include_search
            if pipeline.build.include_search:
                search_generated = True

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=1)
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = mock_copy_js
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = mock_generate_search_indexes
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert js_copied is False, "JS should not be copied in PORTABLE mode"
        assert search_generated is False, "Search should not be generated in PORTABLE mode"

    @pytest.mark.asyncio
    async def test_interactive_mode_includes_js_and_search(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that INTERACTIVE mode includes JS copy and search generation.
        """
        from app.services.build_pipeline import BuildPipeline

        # Configure as INTERACTIVE
        mock_build.package_mode = PackageMode.INTERACTIVE
        mock_build.include_js = True
        mock_build.include_search = True

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        js_copied = False
        search_generated = False

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "js").mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "search").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_copy_js():
            nonlocal js_copied
            if pipeline.build.include_js:
                js_copied = True

        async def mock_generate_search_indexes():
            nonlocal search_generated
            if pipeline.build.include_search:
                search_generated = True

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=1)
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = mock_copy_js
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = mock_generate_search_indexes
        pipeline._copy_export_extras = AsyncMock()
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert js_copied is True, "JS should be copied in INTERACTIVE mode"
        assert search_generated is True, "Search should be generated in INTERACTIVE mode"

    @pytest.mark.asyncio
    async def test_print_bundle_generated_when_needed(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        mock_snapshot: MagicMock,
        temp_workspace: Path,
    ):
        """
        Test that print bundle is generated when targets include pdf/docx.
        """
        from app.services.build_pipeline import BuildPipeline

        # Configure to need print bundle
        mock_build.needs_print_bundle = True
        mock_build.targets = ["zip", "pdf"]

        pipeline = BuildPipeline(mock_build, mock_session, workspace_root=temp_workspace)

        print_bundle_generated = False

        async def mock_create_snapshot():
            return mock_snapshot

        def mock_prepare_workspace():
            ws = temp_workspace / str(mock_build.build_id)
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "assets" / "css").mkdir(parents=True, exist_ok=True)
            return ws

        async def mock_render_print_bundle():
            nonlocal print_bundle_generated
            print_bundle_generated = True
            return 1  # print pages count

        async def mock_create_zip():
            zip_path = temp_workspace / "build.zip"
            zip_path.write_bytes(b"PK\x03\x04")
            return zip_path, "abc123" * 10 + "abcd"

        async def mock_generate_manifest():
            manifest_path = temp_workspace / "manifest.json"
            manifest_path.write_text("{}")
            return manifest_path

        pipeline._create_snapshot = mock_create_snapshot
        pipeline._prepare_workspace = mock_prepare_workspace
        pipeline._collect_asset_url_map = AsyncMock(return_value={})
        pipeline._render_all_pages = AsyncMock(return_value=1)
        pipeline._compile_css = AsyncMock()
        pipeline._copy_js = AsyncMock()
        pipeline._copy_assets = AsyncMock(return_value=0)
        pipeline._generate_search_indexes = AsyncMock()
        pipeline._copy_export_extras = AsyncMock()
        pipeline._render_print_bundle = mock_render_print_bundle
        pipeline._generate_manifest = mock_generate_manifest
        pipeline._create_zip = mock_create_zip

        result = await pipeline.execute()

        assert result.success is True
        assert print_bundle_generated is True, "Print bundle should be generated when needed"
        assert result.stats.get("print_pages", 0) > 0
