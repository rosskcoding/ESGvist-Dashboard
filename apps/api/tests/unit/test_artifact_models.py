"""
Unit tests for Export v2 artifact models and enums.

Tests:
- ArtifactFormat and ArtifactStatus enums
- ReleaseBuildArtifact model
- ReleaseBuild.build_options and helper methods
"""

import pytest
from uuid import uuid4

from app.domain.models.enums import ArtifactFormat, ArtifactStatus


class TestArtifactEnums:
    """Tests for artifact-related enums."""

    def test_artifact_format_values(self):
        """ArtifactFormat should have correct values."""
        assert ArtifactFormat.ZIP.value == "zip"
        assert ArtifactFormat.PRINT_HTML.value == "print_html"
        assert ArtifactFormat.PDF.value == "pdf"
        assert ArtifactFormat.DOCX.value == "docx"

    def test_artifact_format_all_values(self):
        """ArtifactFormat should have exactly 4 values."""
        values = [e.value for e in ArtifactFormat]
        assert len(values) == 4
        assert set(values) == {"zip", "print_html", "pdf", "docx"}

    def test_artifact_status_values(self):
        """ArtifactStatus should have correct values."""
        assert ArtifactStatus.QUEUED.value == "queued"
        assert ArtifactStatus.PROCESSING.value == "processing"
        assert ArtifactStatus.DONE.value == "done"
        assert ArtifactStatus.FAILED.value == "failed"
        assert ArtifactStatus.CANCELLED.value == "cancelled"

    def test_artifact_status_all_values(self):
        """ArtifactStatus should have exactly 5 values."""
        values = [e.value for e in ArtifactStatus]
        assert len(values) == 5
        assert set(values) == {"queued", "processing", "done", "failed", "cancelled"}


class TestReleaseBuildArtifactModel:
    """Tests for ReleaseBuildArtifact model."""

    def test_artifact_is_ready_when_done_with_path(self):
        """is_ready should return True when status is DONE and path exists."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.PDF,
            status=ArtifactStatus.DONE,
            path="/path/to/file.pdf",
        )
        assert artifact.is_ready is True

    def test_artifact_not_ready_when_processing(self):
        """is_ready should return False when status is not DONE."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.PDF,
            status=ArtifactStatus.PROCESSING,
            path="/path/to/file.pdf",
        )
        assert artifact.is_ready is False

    def test_artifact_not_ready_when_no_path(self):
        """is_ready should return False when path is None."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.PDF,
            status=ArtifactStatus.DONE,
            path=None,
        )
        assert artifact.is_ready is False

    def test_artifact_filename_pdf(self):
        """filename should generate correct PDF filename."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.PDF,
            locale="ru",
            profile="audit",
        )
        assert artifact.filename == "report-ru-audit.pdf"

    def test_artifact_filename_docx(self):
        """filename should generate correct DOCX filename."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.DOCX,
            locale="en",
            profile=None,
        )
        assert artifact.filename == "report-en.docx"

    def test_artifact_filename_zip(self):
        """filename should generate correct ZIP filename."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.ZIP,
            locale=None,
            profile=None,
        )
        assert artifact.filename == "report.zip"

    def test_artifact_repr(self):
        """__repr__ should return readable string."""
        from app.domain.models import ReleaseBuildArtifact

        artifact = ReleaseBuildArtifact(
            build_id=uuid4(),
            format=ArtifactFormat.PDF,
            status=ArtifactStatus.QUEUED,
        )
        assert "pdf" in repr(artifact).lower()
        assert "queued" in repr(artifact).lower()


class TestReleaseBuildOptions:
    """Tests for ReleaseBuild.build_options functionality."""

    def test_targets_default_zip(self):
        """targets should return default targets when build_options is None."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options=None,
        )
        assert build.targets == ["zip", "print_html"]

    def test_targets_from_options(self):
        """targets should return value from build_options."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options={"targets": ["zip", "pdf", "docx"]},
        )
        assert build.targets == ["zip", "pdf", "docx"]

    def test_needs_print_bundle_false(self):
        """needs_print_bundle should return False when only zip requested."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options={"targets": ["zip"]},
        )
        assert build.needs_print_bundle is False

    def test_needs_print_bundle_true_pdf(self):
        """needs_print_bundle should return True when pdf requested."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options={"targets": ["zip", "pdf"]},
        )
        assert build.needs_print_bundle is True

    def test_needs_print_bundle_true_docx(self):
        """needs_print_bundle should return True when docx requested."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options={"targets": ["docx"]},
        )
        assert build.needs_print_bundle is True

    def test_get_option_exists(self):
        """get_option should return value when key exists."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options={"pdf_profile": "audit", "chart_scale": 2},
        )
        assert build.get_option("pdf_profile") == "audit"
        assert build.get_option("chart_scale") == 2

    def test_get_option_default(self):
        """get_option should return default when key doesn't exist."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options={},
        )
        assert build.get_option("pdf_profile", "audit") == "audit"
        assert build.get_option("nonexistent") is None

    def test_get_option_none_options(self):
        """get_option should return default when build_options is None."""
        from app.domain.models import ReleaseBuild
        from app.domain.models.enums import BuildType, BuildStatus, BuildScope, PackageMode

        build = ReleaseBuild(
            report_id=uuid4(),
            build_type=BuildType.DRAFT,
            status=BuildStatus.QUEUED,
            theme_slug="default",
            locales=["ru"],
            package_mode=PackageMode.PORTABLE,
            scope=BuildScope.FULL,
            build_options=None,
        )
        assert build.get_option("pdf_profile", "audit") == "audit"

