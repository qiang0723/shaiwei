from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from shaiwei.provenance import write_release_manifest
from shaiwei.release_build_context import (
    ReleaseBuildContextError,
    prepare_scheduler_build_context,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _write(root / ".gitignore", ".release/\n.env\ndata/\nlogs/\n")
    _write(root / ".dockerignore", ".git\n.release\n.env\ndata\nledger\nlogs\n")
    _write(root / "Dockerfile", "FROM scratch\nCOPY src /workspace/src\n")
    _write(root / "src/app.py", "VALUE = 1\n")
    _write(root / "config/app.yaml", "version: 1\n")
    _write(root / "templates/message.txt", "hello\n")
    _write(root / "tests/test_app.py", "def test_value():\n    assert True\n")
    _write(root / "ledger/runtime.csv", "id,status\n1,PASS\n")
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release-test@example.invalid",
        "commit",
        "-m",
        "initial",
    )
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    return root, root / ".release/scheduler-build-contexts"


def test_archive_context_allows_runtime_changes_and_excludes_noncontrolled_files(
    tmp_path: Path,
) -> None:
    root, parent = _repository(tmp_path)
    _write(root / "ledger/runtime.csv", "id,status\n1,PASS\n2,PASS\n")
    _write(root / "docs/user-draft.md", "draft\n")
    _write(root / ".env", "SECRET=not-read\n")
    _write(root / "data/raw/private.txt", "not copied\n")
    _write(root / "logs/runtime.log", "not copied\n")

    with prepare_scheduler_build_context(
        project_root=root,
        context_parent=parent,
    ) as source:
        assert source.git_head == _git(root, "rev-parse", "HEAD")
        assert (source.path / "src/app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
        assert not (source.path / "ledger").exists()
        assert not (source.path / "docs/user-draft.md").exists()
        assert not (source.path / ".env").exists()
        assert not (source.path / "data").exists()
        assert not (source.path / "logs").exists()
        rebuilt = write_release_manifest(tmp_path / "rebuilt.json", root=source.path)
        assert rebuilt["code_snapshot_sha256"] == source.code_snapshot_sha256
        assert rebuilt["file_count"] == source.file_count
        run_root = source.path.parent

    assert not run_root.exists()


@pytest.mark.parametrize(
    "relative",
    ["src/app.py", "config/app.yaml", "templates/message.txt", "tests/test_app.py"],
)
def test_archive_context_rejects_tracked_controlled_changes(
    tmp_path: Path,
    relative: str,
) -> None:
    root, parent = _repository(tmp_path)
    _write(root / relative, "changed\n")

    with pytest.raises(ReleaseBuildContextError, match="controlled inputs differ"):
        with prepare_scheduler_build_context(project_root=root, context_parent=parent):
            pass


def test_archive_context_rejects_untracked_controlled_input(tmp_path: Path) -> None:
    root, parent = _repository(tmp_path)
    _write(root / "src/untracked.py", "VALUE = 2\n")

    with pytest.raises(ReleaseBuildContextError, match="src/untracked.py"):
        with prepare_scheduler_build_context(project_root=root, context_parent=parent):
            pass


def test_archive_context_rejects_controlled_symlink(tmp_path: Path) -> None:
    root, parent = _repository(tmp_path)
    (root / "src/app.py").unlink()
    (root / "src/app.py").symlink_to("../Dockerfile")
    _git(root, "add", "src/app.py")
    _git(
        root,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release-test@example.invalid",
        "commit",
        "-m",
        "controlled symlink",
    )
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")

    with pytest.raises(ReleaseBuildContextError, match="unsupported member"):
        with prepare_scheduler_build_context(project_root=root, context_parent=parent):
            pass


def test_archive_context_rejects_unpushed_head(tmp_path: Path) -> None:
    root, parent = _repository(tmp_path)
    _write(root / "README.md", "new commit\n")
    _git(root, "add", "README.md")
    _git(
        root,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release-test@example.invalid",
        "commit",
        "-m",
        "unpushed",
    )

    with pytest.raises(ReleaseBuildContextError, match="differs from local origin/main"):
        with prepare_scheduler_build_context(project_root=root, context_parent=parent):
            pass


def test_archive_context_rejects_nonignored_or_external_parent(tmp_path: Path) -> None:
    root, _parent = _repository(tmp_path)
    with pytest.raises(ReleaseBuildContextError, match="not Git ignored"):
        with prepare_scheduler_build_context(
            project_root=root,
            context_parent=root / "release-context",
        ):
            pass
    with pytest.raises(ReleaseBuildContextError, match="inside the project"):
        with prepare_scheduler_build_context(
            project_root=root,
            context_parent=tmp_path / "external-context",
        ):
            pass


def test_archive_context_rechecks_controlled_tree_after_archive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root, parent = _repository(tmp_path)
    from shaiwei import release_build_context

    original = release_build_context._archive_revision

    def archive_then_mutate(project, revision, names, archive_path):
        original(project, revision, names, archive_path)
        _write(project / "src/app.py", "changed during archive\n")

    monkeypatch.setattr(release_build_context, "_archive_revision", archive_then_mutate)
    with pytest.raises(ReleaseBuildContextError, match="controlled inputs differ"):
        with prepare_scheduler_build_context(project_root=root, context_parent=parent):
            pass
    assert not parent.exists() or not any(parent.iterdir())
