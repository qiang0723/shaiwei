from pathlib import Path

import pytest

from shaiwei import provenance


def test_code_snapshot_hashes_content_but_excludes_append_only_evidence(monkeypatch, tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "ledger").mkdir()
    (tmp_path / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "ledger/experiments.csv").write_text("first\n", encoding="utf-8")
    (tmp_path / "STATE.md").write_text("building\n", encoding="utf-8")

    class Result:
        def __init__(self, stdout: bytes):
            self.stdout = stdout

    def fake_run(argv, **_kwargs):
        if "--others" in argv:
            return Result(b"")
        return Result(b"src/app.py\0ledger/experiments.csv\0STATE.md\0")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(provenance.subprocess, "run", fake_run)
    first = provenance.code_snapshot_sha256()
    (tmp_path / "ledger/experiments.csv").write_text("second\n", encoding="utf-8")
    (tmp_path / "STATE.md").write_text("complete\n", encoding="utf-8")
    assert provenance.code_snapshot_sha256() == first
    (tmp_path / "src/app.py").write_text("value = 2\n", encoding="utf-8")
    assert provenance.code_snapshot_sha256() != first


def test_release_manifest_binds_exact_controlled_tree(monkeypatch, tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "config/settings.yaml").write_text("runtime: {}\n", encoding="utf-8")
    (tmp_path / "data/runtime.json").write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "release-manifest.json"

    document = provenance.write_release_manifest(manifest, root=tmp_path)
    expected = document["code_snapshot_sha256"]
    assert provenance.verify_release_manifest(manifest, root=tmp_path) == expected

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(provenance.RELEASE_MANIFEST_ENV, str(manifest))
    assert provenance.code_snapshot_sha256() == expected

    (tmp_path / "data/runtime.json").write_text('{"changed": true}\n', encoding="utf-8")
    assert provenance.code_snapshot_sha256() == expected
    (tmp_path / "src/app.py").write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="content differs"):
        provenance.code_snapshot_sha256()


def test_release_manifest_rejects_added_controlled_file(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    manifest = tmp_path / "release-manifest.json"
    provenance.write_release_manifest(manifest, root=tmp_path)
    (tmp_path / "src/unregistered.py").write_text("value = 2\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="file set differs"):
        provenance.verify_release_manifest(manifest, root=tmp_path)


def test_release_git_head_uses_valid_embedded_revision_without_git(monkeypatch):
    monkeypatch.setenv(provenance.RELEASE_GIT_HEAD_ENV, "A" * 40)
    monkeypatch.setattr(
        provenance.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Git must not run")),
    )

    assert provenance.git_head() == "a" * 40


def test_release_git_head_rejects_invalid_embedded_revision(monkeypatch):
    monkeypatch.setenv(provenance.RELEASE_GIT_HEAD_ENV, "not-a-commit")

    with pytest.raises(RuntimeError, match="revision is invalid"):
        provenance.git_head()
