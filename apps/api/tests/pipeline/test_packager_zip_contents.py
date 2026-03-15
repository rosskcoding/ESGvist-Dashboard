"""
Tests for ZIP Packager contents validation.

These tests verify that the packager correctly:
- Includes print bundle and key files
- Excludes secrets and temp files
- Protects against path traversal
- Generates valid manifest

Spec reference: Zip / Print Bundle Packager Tests (TEST-01 to TEST-06)
"""

import json
import os
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.services.packager import (
    EXCLUDED_DIRS,
    EXCLUDED_PATTERNS,
    package_zip,
    validate_zip_contents,
)


class TestZipPackagerContents:
    """Tests for ZIP packager file inclusion/exclusion logic."""

    @pytest.fixture
    def workspace(self) -> Path:
        """Create a temporary workspace with standard structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            yield workspace

    @pytest.fixture
    def standard_workspace(self, workspace: Path) -> Path:
        """
        Create workspace with standard structure per spec:

        workspace/
          manifest.json
          report.json
          assets/
            logo.svg
            styles.css
          print/
            index.html
            sections/
              s1.html
            assets/
              print.css
        """
        # Create directories
        (workspace / "assets").mkdir()
        (workspace / "print").mkdir()
        (workspace / "print" / "sections").mkdir()
        (workspace / "print" / "assets").mkdir()

        # Create manifest.json
        manifest = {
            "build_id": "test-build-123",
            "report_id": "test-report-456",
            "created_at": "2025-01-01T00:00:00Z",
            "version": "1.0.0",
        }
        (workspace / "build-manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # Create report.json
        (workspace / "report.json").write_text(
            '{"title": "Test Report"}', encoding="utf-8"
        )

        # Create assets
        (workspace / "assets" / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
        )
        (workspace / "assets" / "styles.css").write_text(
            "body { margin: 0; }", encoding="utf-8"
        )

        # Create print bundle with cross-reference
        print_html = """<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="./assets/print.css">
</head>
<body>
    <h1>Print Index</h1>
    <a href="./sections/s1.html">Section 1</a>
</body>
</html>"""
        (workspace / "print" / "index.html").write_text(print_html, encoding="utf-8")

        (workspace / "print" / "sections" / "s1.html").write_text(
            "<html><body><h2>Section 1</h2></body></html>", encoding="utf-8"
        )

        (workspace / "print" / "assets" / "print.css").write_text(
            "@page { size: A4; }\nbody { font-family: serif; }", encoding="utf-8"
        )

        return workspace

    # =========================================================================
    # TEST-01: ZIP includes print bundle and key files (happy path)
    # =========================================================================

    def test_01_zip_includes_print_bundle_and_key_files(
        self, standard_workspace: Path
    ):
        """
        TEST-01: ZIP should include print bundle and key files.

        Verify that:
        - print/index.html is included
        - print/sections/s1.html is included
        - print/assets/print.css is included
        - assets/logo.svg is included
        - assets/styles.css is included
        - Paths are relative (no workspace/ prefix)
        """
        # Arrange: workspace created by fixture
        out_path = standard_workspace.parent / "output.zip"

        # Act
        zip_path, sha256 = package_zip(standard_workspace, out_path)

        # Assert
        assert zip_path.exists()
        assert len(sha256) == 64  # SHA256 hex digest

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Print bundle files must be present
            assert "print/index.html" in names
            assert "print/sections/s1.html" in names
            assert "print/assets/print.css" in names

            # Root assets
            assert "assets/logo.svg" in names
            assert "assets/styles.css" in names

            # Manifest
            assert "build-manifest.json" in names

            # Paths should NOT contain workspace/ prefix
            for name in names:
                assert not name.startswith("workspace/"), (
                    f"Path should be relative, got: {name}"
                )

    def test_01_zip_content_is_readable(self, standard_workspace: Path):
        """Verify that ZIP content can be read correctly."""
        out_path = standard_workspace.parent / "output.zip"
        zip_path, _ = package_zip(standard_workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Read print CSS content
            css_content = zf.read("print/assets/print.css").decode("utf-8")
            assert "@page" in css_content
            assert "font-family: serif" in css_content

    # =========================================================================
    # TEST-02: ZIP excludes secrets and temp files
    # =========================================================================

    def test_02_zip_excludes_secrets_and_junk(self, standard_workspace: Path):
        """
        TEST-02: ZIP should exclude secrets and temp/junk files.

        Verify exclusion of:
        - .env, secrets.json
        - tmp/debug.log
        - .git/config
        - __pycache__/*
        """
        # Arrange: Add secret and junk files
        (standard_workspace / ".env").write_text("SECRET_KEY=abc123")
        (standard_workspace / "secrets.json").write_text('{"api_key": "secret"}')

        # Create tmp directory with log
        (standard_workspace / "tmp").mkdir()
        (standard_workspace / "tmp" / "debug.log").write_text("DEBUG: test")

        # Create .git directory
        (standard_workspace / ".git").mkdir()
        (standard_workspace / ".git" / "config").write_text("[core]")

        # Create __pycache__
        (standard_workspace / "__pycache__").mkdir()
        (standard_workspace / "__pycache__" / "module.cpython-311.pyc").write_bytes(
            b"\x00\x00\x00\x00"
        )

        # Create node_modules (should be excluded)
        (standard_workspace / "node_modules").mkdir()
        (standard_workspace / "node_modules" / "package.json").write_text('{}')

        out_path = standard_workspace.parent / "output.zip"

        # Act
        zip_path, _ = package_zip(standard_workspace, out_path)

        # Assert
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Secrets must NOT be present
            assert ".env" not in names
            assert "secrets.json" not in names

            # Tmp files must NOT be present
            assert "tmp/debug.log" not in names
            assert not any(n.startswith("tmp/") for n in names)

            # Git must NOT be present
            assert ".git/config" not in names
            assert not any(n.startswith(".git/") for n in names)

            # __pycache__ must NOT be present
            assert not any("__pycache__" in n for n in names)

            # node_modules must NOT be present
            assert not any("node_modules" in n for n in names)

            # But valid files SHOULD be present
            assert "print/index.html" in names
            assert "assets/logo.svg" in names

    def test_02_excludes_key_files(self, workspace: Path):
        """Test that various secret file patterns are excluded."""
        # Create files matching secret patterns
        test_files = [
            ("private.key", "PRIVATE KEY"),
            ("server.pem", "-----BEGIN CERTIFICATE-----"),
            ("api_secret.txt", "secret_token"),
            ("id_rsa", "RSA PRIVATE KEY"),
            ("credentials.json", '{"password": "123"}'),
            (".env.production", "PROD_KEY=xyz"),
            ("cert.p12", b"\x00\x01\x02"),
            ("app.log", "2025-01-01 ERROR"),
            ("backup.tmp", "temp data"),
        ]

        for filename, content in test_files:
            path = workspace / filename
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)

        # Add one valid file
        (workspace / "index.html").write_text("<html></html>")

        out_path = workspace.parent / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Only index.html should be included
            assert names == ["index.html"]

    # =========================================================================
    # TEST-03: Protection against path traversal / unsafe paths
    # =========================================================================

    def test_03_validates_no_path_traversal_in_output(
        self, standard_workspace: Path
    ):
        """
        TEST-03: ZIP entries must not contain path traversal.

        Verify that all entries:
        - Do not contain '..'
        - Do not start with '/'
        - Do not contain backslash
        """
        out_path = standard_workspace.parent / "output.zip"
        zip_path, _ = package_zip(standard_workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                # No parent directory traversal
                assert ".." not in name, f"Path traversal detected: {name}"

                # No absolute paths
                assert not name.startswith("/"), f"Absolute path detected: {name}"

                # No backslashes (Windows-style)
                assert "\\" not in name, f"Backslash in path: {name}"

                # No null bytes
                assert "\x00" not in name, f"Null byte in path: {name}"

                # No drive letters (Windows)
                assert ":" not in name, f"Drive letter in path: {name}"

    def test_03_strict_mode_raises_on_unsafe_arcname(self, workspace: Path):
        """
        Strict mode should raise ValueError on unsafe paths.

        Note: Creating actual files with '..' in name is OS-dependent.
        This test verifies the validation logic through the safe_path check.
        """
        from app.services.packager import _is_safe_path

        # Test path validation logic directly
        assert _is_safe_path("print/index.html") is True
        assert _is_safe_path("assets/logo.svg") is True

        # Unsafe paths
        assert _is_safe_path("../evil.txt") is False
        assert _is_safe_path("/absolute/path.txt") is False
        assert _is_safe_path("path\\with\\backslash.txt") is False
        assert _is_safe_path("path\x00null.txt") is False
        assert _is_safe_path("C:windows.txt") is False

    def test_03_symlink_escape_raises_in_strict_mode(self, workspace: Path):
        """
        If workspace contains a file that resolves outside workspace via symlink,
        packager must refuse to build the ZIP in strict_mode.
        """
        (workspace / "normal.txt").write_text("normal content", encoding="utf-8")

        # External file outside workspace
        external_dir = workspace.parent / "external"
        external_dir.mkdir(parents=True, exist_ok=True)
        external_file = external_dir / "evil.txt"
        external_file.write_text("EVIL", encoding="utf-8")

        # Symlink inside workspace pointing outside
        link_path = workspace / "evil_link.txt"
        try:
            link_path.symlink_to(external_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are not supported or not permitted on this platform")

        out_path = workspace.parent / "output.zip"
        with pytest.raises(ValueError, match="outside workspace|unresolvable"):
            package_zip(workspace, out_path, strict_mode=True)

    def test_03_symlink_escape_is_skipped_in_non_strict_mode(self, workspace: Path):
        """In non-strict mode, unsafe symlinks should be skipped (not included)."""
        (workspace / "normal.txt").write_text("normal content", encoding="utf-8")

        external_dir = workspace.parent / "external"
        external_dir.mkdir(parents=True, exist_ok=True)
        external_file = external_dir / "evil.txt"
        external_file.write_text("EVIL", encoding="utf-8")

        link_path = workspace / "evil_link.txt"
        try:
            link_path.symlink_to(external_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are not supported or not permitted on this platform")

        out_path = workspace.parent / "output.zip"
        zip_path, _ = package_zip(workspace, out_path, strict_mode=False)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "normal.txt" in names
            assert "evil_link.txt" not in names

    # =========================================================================
    # TEST-04: Manifest is present and valid
    # =========================================================================

    def test_04_manifest_present_and_valid_json(self, standard_workspace: Path):
        """
        TEST-04: Manifest should be present and valid JSON.

        Verify:
        - build-manifest.json exists in ZIP
        - Content is valid JSON
        - Required keys are present
        """
        out_path = standard_workspace.parent / "output.zip"
        zip_path, _ = package_zip(standard_workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Manifest should exist
            assert "build-manifest.json" in zf.namelist()

            # Read and parse
            manifest_bytes = zf.read("build-manifest.json")
            manifest = json.loads(manifest_bytes.decode("utf-8"))

            # Required keys should be present
            assert "build_id" in manifest
            assert "report_id" in manifest
            assert "created_at" in manifest
            assert "version" in manifest

            # Values should be non-empty
            assert manifest["build_id"]
            assert manifest["report_id"]

    def test_04_manifest_json_syntax(self, workspace: Path):
        """Verify manifest is syntactically correct JSON."""
        # Create minimal manifest
        manifest = {
            "build_id": "abc-123",
            "report_id": "def-456",
            "created_at": "2025-01-01T00:00:00Z",
            "version": "1.0.0",
            "files": {"index.html": {"sha256": "abc123", "size": 100}},
        }
        (workspace / "build-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (workspace / "index.html").write_text("<html></html>")

        out_path = workspace.parent / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            content = zf.read("build-manifest.json").decode("utf-8")

            # Must not raise
            parsed = json.loads(content)

            # Verify structure preserved
            assert parsed["files"]["index.html"]["sha256"] == "abc123"

    # =========================================================================
    # TEST-05: Print bundle is self-contained (asset references)
    # =========================================================================

    def test_05_print_bundle_self_contained(self, standard_workspace: Path):
        """
        TEST-05: Print bundle should be self-contained.

        Verify that files referenced in print/index.html exist in ZIP:
        - If index.html references assets/print.css, that file should exist
        """
        out_path = standard_workspace.parent / "output.zip"
        zip_path, _ = package_zip(standard_workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())

            # Read print/index.html
            html_content = zf.read("print/index.html").decode("utf-8")

            # Extract href references
            import re
            hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_content)

            for href in hrefs:
                # Skip external URLs
                if href.startswith("http://") or href.startswith("https://"):
                    continue

                # Resolve relative path from print/ directory
                if href.startswith("./"):
                    resolved = "print/" + href[2:]
                elif href.startswith("../"):
                    # Would go to workspace root
                    resolved = href[3:]
                else:
                    resolved = "print/" + href

                # Normalize path
                resolved = resolved.replace("//", "/")

                # Check file exists
                assert resolved in names, (
                    f"Referenced file missing: {href} -> {resolved}\n"
                    f"Available files: {sorted(names)}"
                )

    def test_05_print_css_referenced_exists(self, standard_workspace: Path):
        """Specific check: print.css referenced in index.html exists."""
        out_path = standard_workspace.parent / "output.zip"
        zip_path, _ = package_zip(standard_workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # print/index.html has: <link href="./assets/print.css">
            # This resolves to print/assets/print.css
            assert "print/assets/print.css" in zf.namelist()

            # Verify content is valid CSS
            css = zf.read("print/assets/print.css").decode("utf-8")
            assert "@page" in css

    # =========================================================================
    # TEST-06: Size/composition doesn't bloat
    # =========================================================================

    def test_06_excludes_large_directories(self, workspace: Path):
        """
        TEST-06: Large directories like node_modules should be excluded.

        Verify that accidentally including huge directories doesn't bloat ZIP.
        """
        # Create node_modules with many files
        node_modules = workspace / "node_modules"
        node_modules.mkdir()

        for i in range(100):
            (node_modules / f"package_{i}").mkdir()
            (node_modules / f"package_{i}" / "index.js").write_text(f"// pkg {i}")

        # Create tmp with many log files
        tmp_dir = workspace / "tmp"
        tmp_dir.mkdir()

        for i in range(100):
            (tmp_dir / f"debug_{i}.log").write_text(f"Log entry {i}\n" * 100)

        # Create legitimate files
        (workspace / "index.html").write_text("<html></html>")
        (workspace / "print").mkdir()
        (workspace / "print" / "report.html").write_text("<html>Report</html>")

        out_path = workspace.parent / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Should have very few files (just the legitimate ones)
            assert len(names) < 10, f"Too many files in ZIP: {len(names)}"

            # node_modules excluded
            assert not any("node_modules" in n for n in names)

            # tmp excluded
            assert not any("tmp/" in n or n == "tmp" for n in names)

            # Legitimate files present
            assert "index.html" in names
            assert "print/report.html" in names

    def test_06_file_count_threshold(self, workspace: Path):
        """Verify total file count stays reasonable."""
        # Create a reasonable structure
        (workspace / "index.html").write_text("<html></html>")
        (workspace / "assets").mkdir()

        for i in range(20):
            (workspace / "assets" / f"file_{i}.css").write_text(f".class{i} {{}}")

        (workspace / "print").mkdir()
        (workspace / "print" / "report.html").write_text("<html></html>")

        out_path = workspace.parent / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Reasonable threshold for a typical report
            assert len(names) < 200, (
                f"ZIP has too many files ({len(names)}), "
                "may indicate junk included"
            )


class TestValidateZipContents:
    """Tests for the validate_zip_contents helper function."""

    def test_validation_detects_print_bundle(self, tmp_path: Path):
        """Validation should detect presence of print bundle."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "print").mkdir()
        (workspace / "print" / "index.html").write_text("<html></html>")

        out_path = tmp_path / "test.zip"
        zip_path, _ = package_zip(workspace, out_path)

        result = validate_zip_contents(zip_path)

        assert result["has_print_bundle"] is True
        assert "print/index.html" in result["files"]

    def test_validation_detects_manifest(self, tmp_path: Path):
        """Validation should detect presence of manifest."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        manifest = {"build_id": "test", "report_id": "test"}
        (workspace / "build-manifest.json").write_text(json.dumps(manifest))

        out_path = tmp_path / "test.zip"
        zip_path, _ = package_zip(workspace, out_path)

        result = validate_zip_contents(zip_path)

        assert result["has_manifest"] is True


class TestPackagerEdgeCases:
    """Edge case tests for packager robustness."""

    def test_empty_workspace(self, tmp_path: Path):
        """Empty workspace should produce empty ZIP."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        out_path = tmp_path / "output.zip"
        zip_path, sha256 = package_zip(workspace, out_path)

        assert zip_path.exists()

        with zipfile.ZipFile(zip_path, "r") as zf:
            assert len(zf.namelist()) == 0

    def test_nonexistent_workspace_raises(self, tmp_path: Path):
        """Non-existent workspace should raise ValueError."""
        workspace = tmp_path / "does_not_exist"
        out_path = tmp_path / "output.zip"

        with pytest.raises(ValueError, match="does not exist"):
            package_zip(workspace, out_path)

    def test_workspace_is_file_raises(self, tmp_path: Path):
        """Workspace that is a file should raise ValueError."""
        workspace = tmp_path / "not_a_dir"
        workspace.write_text("I am a file")

        out_path = tmp_path / "output.zip"

        with pytest.raises(ValueError, match="not a directory"):
            package_zip(workspace, out_path)

    def test_binary_files_preserved(self, tmp_path: Path):
        """Binary files should be preserved exactly."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create binary file with specific bytes
        binary_data = bytes(range(256))
        (workspace / "binary.bin").write_bytes(binary_data)

        out_path = tmp_path / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            extracted = zf.read("binary.bin")
            assert extracted == binary_data

    def test_unicode_filenames(self, tmp_path: Path):
        """Unicode filenames should be handled correctly."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create files with unicode names
        (workspace / "file.txt").write_text("Sample text")
        (workspace / "café.txt").write_text("Unicode filename content")

        out_path = tmp_path / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "file.txt" in names
            assert "café.txt" in names

            # Content preserved
            assert zf.read("café.txt").decode("utf-8") == "Unicode filename content"

    def test_deeply_nested_structure(self, tmp_path: Path):
        """Deeply nested directories should be handled."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create deep nesting
        deep_path = workspace
        for i in range(10):
            deep_path = deep_path / f"level_{i}"
            deep_path.mkdir()

        (deep_path / "deep_file.txt").write_text("deep content")

        out_path = tmp_path / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # File should be included with full path
            expected = "/".join(f"level_{i}" for i in range(10)) + "/deep_file.txt"
            assert expected in zf.namelist()

    def test_include_print_false(self, tmp_path: Path):
        """When include_print=False, print/ should be excluded."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html></html>")
        (workspace / "print").mkdir()
        (workspace / "print" / "report.html").write_text("<html></html>")

        out_path = tmp_path / "output.zip"
        zip_path, _ = package_zip(workspace, out_path, include_print=False)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            assert "index.html" in names
            assert not any(n.startswith("print/") for n in names)


class TestExcludedPatterns:
    """Tests verifying all documented exclusion patterns."""

    @pytest.mark.parametrize("filename,should_exclude", [
        # Environment files
        (".env", True),
        (".env.local", True),
        (".env.production", True),
        # Key/cert files
        ("private.key", True),
        ("server.pem", True),
        ("cert.p12", True),
        ("keystore.pfx", True),
        # Secret files
        ("secrets.json", True),
        ("api_secret.txt", True),
        ("my_secret_config.yaml", True),
        # SSH keys
        ("id_rsa", True),
        ("id_rsa.pub", True),
        # Credentials
        ("credentials.json", True),
        ("credentials_backup.txt", True),
        # Logs
        ("app.log", True),
        ("debug.log", True),
        ("error.log", True),
        # Temp files
        ("file.tmp", True),
        ("backup.temp", True),
        ("file.swp", True),
        ("file~", True),
        # System files
        (".DS_Store", True),
        ("Thumbs.db", True),
        ("desktop.ini", True),
        # Valid files (should NOT be excluded)
        ("index.html", False),
        ("styles.css", False),
        ("app.js", False),
        ("logo.svg", False),
        ("data.json", False),
        ("config.yaml", False),
        ("secret_garden.png", True),  # Contains "secret"
    ])
    def test_filename_exclusion(self, filename: str, should_exclude: bool):
        """Test that specific filenames are correctly included/excluded."""
        from app.services.packager import _is_excluded_by_pattern

        result = _is_excluded_by_pattern(filename)
        assert result == should_exclude, (
            f"File '{filename}' exclusion mismatch: "
            f"expected {should_exclude}, got {result}"
        )

    @pytest.mark.parametrize("dirname", EXCLUDED_DIRS)
    def test_all_excluded_dirs_blocked(self, dirname: str, tmp_path: Path):
        """Test that all documented excluded directories are blocked."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create excluded directory with a file
        excluded_dir = workspace / dirname
        excluded_dir.mkdir()
        (excluded_dir / "file.txt").write_text("content")

        # Create valid file
        (workspace / "valid.txt").write_text("valid")

        out_path = tmp_path / "output.zip"
        zip_path, _ = package_zip(workspace, out_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            assert "valid.txt" in names
            assert not any(dirname in n for n in names), (
                f"Excluded dir '{dirname}' found in ZIP"
            )
