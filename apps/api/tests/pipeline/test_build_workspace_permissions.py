from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.build_pipeline import BuildPipeline


def _make_pipeline(workspace_root: Path, locales: list[str] | None = None) -> BuildPipeline:
    build = SimpleNamespace(
        build_id=uuid4(),
        report_id=uuid4(),
        locales=locales or ["en"],
    )
    return BuildPipeline(build=build, session=None, workspace_root=workspace_root)


def test_prepare_workspace_creates_expected_structure(tmp_path: Path) -> None:
    pipeline = _make_pipeline(tmp_path, locales=["en", "kk"])
    workspace = pipeline._prepare_workspace()

    assert workspace.exists()
    assert (workspace / "assets" / "css").is_dir()
    assert (workspace / "assets" / "js").is_dir()
    assert (workspace / "assets" / "media").is_dir()
    assert (workspace / "assets" / "search").is_dir()
    assert (workspace / "en" / "sections").is_dir()
    assert (workspace / "kk" / "sections").is_dir()


def test_prepare_workspace_raises_clear_error_when_root_not_writable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pipeline = _make_pipeline(tmp_path)
    original_mkdir = Path.mkdir

    def denied_mkdir(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == tmp_path:
            raise PermissionError("denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", denied_mkdir)

    with pytest.raises(PermissionError) as exc_info:
        pipeline._prepare_workspace()

    message = str(exc_info.value)
    assert "not writable" in message
    assert str(tmp_path) in message
