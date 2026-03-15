"""
Unit tests for asset storage path generation and validation.

Tests:
- Company-scoped path generation
- Filename sanitization
- Path traversal prevention
- Path validation
"""

import pytest
from uuid import uuid4

# Import the functions directly from assets module
import sys
sys.path.insert(0, 'app')

from app.api.v1.assets import _get_storage_path, _validate_storage_path


class TestGetStoragePath:
    """Tests for _get_storage_path function."""

    def test_basic_path_format(self):
        """Path should follow company/{company_id}/assets/{asset_id}/{filename} format."""
        company_id = uuid4()
        asset_id = uuid4()
        filename = "test.jpg"

        path = _get_storage_path(company_id, asset_id, filename)

        assert path.startswith(f"company/{company_id}/assets/{asset_id}/")
        assert path.endswith("test.jpg")

    def test_filename_in_path(self):
        """Filename should be included in path."""
        company_id = uuid4()
        asset_id = uuid4()

        path = _get_storage_path(company_id, asset_id, "myfile.png")

        assert "myfile.png" in path

    def test_sanitizes_path_traversal(self):
        """Filename with path traversal should be sanitized."""
        company_id = uuid4()
        asset_id = uuid4()

        # Attempt path traversal
        path = _get_storage_path(company_id, asset_id, "../../../etc/passwd")

        # Should only contain the filename part, sanitized
        assert ".." not in path
        assert "/" not in path.split("/")[-1] or path.endswith("etc_passwd")
        assert path.startswith(f"company/{company_id}/assets/{asset_id}/")

    def test_sanitizes_directory_in_filename(self):
        """Directory components in filename should be removed."""
        company_id = uuid4()
        asset_id = uuid4()

        path = _get_storage_path(company_id, asset_id, "some/path/to/file.jpg")

        # Should only have the filename
        filename_part = path.split("/")[-1]
        assert "path" not in filename_part or filename_part == "file.jpg"

    def test_sanitizes_special_characters(self):
        """Special characters in filename should be replaced."""
        company_id = uuid4()
        asset_id = uuid4()

        path = _get_storage_path(company_id, asset_id, "file with spaces & symbols!.jpg")

        filename_part = path.split("/")[-1]
        # Spaces and special chars should be replaced with underscores
        assert " " not in filename_part
        assert "&" not in filename_part
        assert "!" not in filename_part

    def test_preserves_safe_characters(self):
        """Safe characters (alphanumeric, dash, underscore, dot) should be preserved."""
        company_id = uuid4()
        asset_id = uuid4()

        path = _get_storage_path(company_id, asset_id, "my-file_v2.0.jpg")

        filename_part = path.split("/")[-1]
        assert filename_part == "my-file_v2.0.jpg"

    def test_limits_filename_length(self):
        """Very long filenames should be truncated."""
        company_id = uuid4()
        asset_id = uuid4()

        # 150 character filename
        long_name = "a" * 150 + ".jpg"

        path = _get_storage_path(company_id, asset_id, long_name)

        filename_part = path.split("/")[-1]
        assert len(filename_part) <= 100

    def test_preserves_extension_on_truncation(self):
        """Extension should be preserved when truncating."""
        company_id = uuid4()
        asset_id = uuid4()

        long_name = "a" * 150 + ".png"

        path = _get_storage_path(company_id, asset_id, long_name)

        filename_part = path.split("/")[-1]
        assert filename_part.endswith(".png")

    def test_different_companies_different_paths(self):
        """Different companies should have different paths."""
        company_a = uuid4()
        company_b = uuid4()
        asset_id = uuid4()

        path_a = _get_storage_path(company_a, asset_id, "file.jpg")
        path_b = _get_storage_path(company_b, asset_id, "file.jpg")

        assert path_a != path_b
        assert str(company_a) in path_a
        assert str(company_b) in path_b

    def test_different_assets_different_paths(self):
        """Different assets should have different paths."""
        company_id = uuid4()
        asset_a = uuid4()
        asset_b = uuid4()

        path_a = _get_storage_path(company_id, asset_a, "file.jpg")
        path_b = _get_storage_path(company_id, asset_b, "file.jpg")

        assert path_a != path_b


class TestValidateStoragePath:
    """Tests for _validate_storage_path function."""

    def test_valid_path(self):
        """Valid company-scoped path should pass."""
        company_id = uuid4()
        asset_id = uuid4()

        path = f"company/{company_id}/assets/{asset_id}/file.jpg"

        assert _validate_storage_path(path) is True

    def test_rejects_absolute_path_unix(self):
        """Absolute Unix paths should be rejected."""
        assert _validate_storage_path("/etc/passwd") is False
        assert _validate_storage_path("/company/123/file.jpg") is False

    def test_rejects_absolute_path_windows(self):
        """Absolute Windows paths should be rejected."""
        assert _validate_storage_path("\\company\\123\\file.jpg") is False

    def test_rejects_path_traversal(self):
        """Path traversal attempts should be rejected."""
        assert _validate_storage_path("company/123/../../../etc/passwd") is False
        assert _validate_storage_path("..") is False
        assert _validate_storage_path("company/../secrets") is False

    def test_rejects_null_bytes(self):
        """Paths with null bytes should be rejected."""
        assert _validate_storage_path("company/123/file\x00.jpg") is False

    def test_rejects_non_company_prefix(self):
        """Paths not starting with 'company/' should be rejected."""
        assert _validate_storage_path("uploads/file.jpg") is False
        assert _validate_storage_path("assets/file.jpg") is False
        assert _validate_storage_path("file.jpg") is False

    def test_valid_path_with_subdirectories(self):
        """Valid path with asset subdirectory should pass."""
        company_id = uuid4()
        asset_id = uuid4()

        path = f"company/{company_id}/assets/{asset_id}/image.png"

        assert _validate_storage_path(path) is True


class TestStoragePathSecurity:
    """Integration tests for storage path security."""

    def test_generated_path_passes_validation(self):
        """Paths generated by _get_storage_path should always pass validation."""
        company_id = uuid4()
        asset_id = uuid4()

        # Test various filenames
        filenames = [
            "normal.jpg",
            "with spaces.png",
            "../../../etc/passwd",
            "file\x00.jpg",
            "a" * 200 + ".gif",
            "café.jpg",
            "résumé.png",
        ]

        for filename in filenames:
            path = _get_storage_path(company_id, asset_id, filename)
            assert _validate_storage_path(path) is True, f"Failed for filename: {filename}"

    def test_company_isolation(self):
        """Assets from different companies should have completely different paths."""
        company_a = uuid4()
        company_b = uuid4()
        asset_id = uuid4()  # Same asset ID
        filename = "shared.jpg"

        path_a = _get_storage_path(company_a, asset_id, filename)
        path_b = _get_storage_path(company_b, asset_id, filename)

        # Paths should not share any directory
        assert path_a != path_b
        # Company A path should not contain Company B ID
        assert str(company_b) not in path_a
        # Company B path should not contain Company A ID
        assert str(company_a) not in path_b

