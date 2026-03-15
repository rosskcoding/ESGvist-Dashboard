"""
Unit tests for reproducible build features.

Tests that:
- ZIP files have deterministic ordering
- ZIP files have fixed timestamps
- JSON is serialized with sorted keys
"""

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path


class TestReproducibleZip:
    """Tests for reproducible ZIP creation."""

    def test_zip_files_sorted_alphabetically(self):
        """ZIP entries should be sorted alphabetically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            workspace = tmpdir_path / "workspace"
            workspace.mkdir()

            # Create files in random order
            (workspace / "zebra.txt").write_text("z")
            (workspace / "alpha.txt").write_text("a")
            (workspace / "middle.txt").write_text("m")
            (workspace / "subdir").mkdir()
            (workspace / "subdir" / "beta.txt").write_text("b")

            # Create ZIP using our reproducible logic
            zip_path = tmpdir_path / "test.zip"

            # Fixed timestamp
            FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

            # Collect and sort files
            all_files = sorted(
                [f for f in workspace.rglob("*") if f.is_file()],
                key=lambda p: str(p.relative_to(workspace)),
            )

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in all_files:
                    arcname = str(file_path.relative_to(workspace))
                    data = file_path.read_bytes()
                    info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_TIMESTAMP)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    file_mode = 0o755 if arcname.endswith(".sh") else 0o644
                    info.create_system = 3  # UNIX
                    info.external_attr = (file_mode & 0xFFFF) << 16
                    zipf.writestr(info, data)

            # Verify order
            with zipfile.ZipFile(zip_path, "r") as zipf:
                names = zipf.namelist()

            assert names == ["alpha.txt", "middle.txt", "subdir/beta.txt", "zebra.txt"]

    def test_zip_fixed_timestamp(self):
        """All ZIP entries should have fixed timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            workspace = tmpdir_path / "workspace"
            workspace.mkdir()

            (workspace / "file1.txt").write_text("content1")
            (workspace / "file2.txt").write_text("content2")

            zip_path = tmpdir_path / "test.zip"
            FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

            all_files = sorted(
                [f for f in workspace.rglob("*") if f.is_file()],
                key=lambda p: str(p.relative_to(workspace)),
            )

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in all_files:
                    arcname = str(file_path.relative_to(workspace))
                    data = file_path.read_bytes()
                    info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_TIMESTAMP)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    file_mode = 0o755 if arcname.endswith(".sh") else 0o644
                    info.create_system = 3  # UNIX
                    info.external_attr = (file_mode & 0xFFFF) << 16
                    zipf.writestr(info, data)

            # Verify timestamps
            with zipfile.ZipFile(zip_path, "r") as zipf:
                for info in zipf.infolist():
                    assert info.date_time == FIXED_TIMESTAMP

    def test_reproducible_hash(self):
        """Two ZIPs from same content should have identical hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create workspace
            workspace = tmpdir_path / "workspace"
            workspace.mkdir()
            (workspace / "a.txt").write_text("hello")
            (workspace / "b.json").write_text('{"key": "value"}')

            FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

            def create_zip(dest: Path) -> str:
                all_files = sorted(
                    [f for f in workspace.rglob("*") if f.is_file()],
                    key=lambda p: str(p.relative_to(workspace)),
                )

                with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in all_files:
                        arcname = str(file_path.relative_to(workspace))
                        data = file_path.read_bytes()
                        info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_TIMESTAMP)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        file_mode = 0o755 if arcname.endswith(".sh") else 0o644
                        info.create_system = 3  # UNIX
                        info.external_attr = (file_mode & 0xFFFF) << 16
                        zipf.writestr(info, data)

                return hashlib.sha256(dest.read_bytes()).hexdigest()

            # Create two ZIPs
            hash1 = create_zip(tmpdir_path / "zip1.zip")
            hash2 = create_zip(tmpdir_path / "zip2.zip")

            assert hash1 == hash2

    def test_zip_preserves_executable_bit_for_sh(self):
        """Shell scripts in ZIP should be marked executable via UNIX mode bits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            workspace = tmpdir_path / "workspace"
            workspace.mkdir()

            sh_path = workspace / "start.sh"
            sh_path.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
            os.chmod(sh_path, 0o755)

            zip_path = tmpdir_path / "test.zip"
            FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

            all_files = sorted(
                [f for f in workspace.rglob("*") if f.is_file()],
                key=lambda p: str(p.relative_to(workspace)),
            )

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in all_files:
                    arcname = str(file_path.relative_to(workspace))
                    data = file_path.read_bytes()
                    info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_TIMESTAMP)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    file_mode = 0o755 if arcname.endswith(".sh") else 0o644
                    info.create_system = 3  # UNIX
                    info.external_attr = (file_mode & 0xFFFF) << 16
                    zipf.writestr(info, data)

            # Verify stored mode in ZIP metadata
            with zipfile.ZipFile(zip_path, "r") as zipf:
                info = zipf.getinfo("start.sh")
                stored_mode = (info.external_attr >> 16) & 0o777
                assert stored_mode == 0o755


class TestCanonicalJson:
    """Tests for canonical JSON serialization."""

    def test_sorted_keys(self):
        """JSON should be serialized with sorted keys."""
        data = {"zebra": 1, "alpha": 2, "middle": 3}

        result = json.dumps(data, sort_keys=True)

        # Keys should appear in alphabetical order
        assert result == '{"alpha": 2, "middle": 3, "zebra": 1}'

    def test_nested_sorted_keys(self):
        """Nested objects should also have sorted keys."""
        data = {
            "z_outer": {"b_inner": 1, "a_inner": 2},
            "a_outer": {"z_inner": 3, "a_inner": 4},
        }

        result = json.dumps(data, sort_keys=True, separators=(",", ":"))

        # Both outer and inner should be sorted
        expected = '{"a_outer":{"a_inner":4,"z_inner":3},"z_outer":{"a_inner":2,"b_inner":1}}'
        assert result == expected

    def test_reproducible_json(self):
        """Same data should produce identical JSON."""
        data1 = {"b": [3, 2, 1], "a": {"nested": True}}
        data2 = {"a": {"nested": True}, "b": [3, 2, 1]}  # Different order

        json1 = json.dumps(data1, sort_keys=True)
        json2 = json.dumps(data2, sort_keys=True)

        assert json1 == json2

