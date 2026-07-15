from pathlib import Path

from shaiwei import provenance


def test_code_snapshot_hashes_content_but_excludes_append_only_evidence(monkeypatch, tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "ledger").mkdir()
    (tmp_path / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "ledger/experiments.csv").write_text("first\n", encoding="utf-8")

    class Result:
        def __init__(self, stdout: bytes):
            self.stdout = stdout

    def fake_run(argv, **_kwargs):
        if "--others" in argv:
            return Result(b"")
        return Result(b"src/app.py\0ledger/experiments.csv\0")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(provenance.subprocess, "run", fake_run)
    first = provenance.code_snapshot_sha256()
    (tmp_path / "ledger/experiments.csv").write_text("second\n", encoding="utf-8")
    assert provenance.code_snapshot_sha256() == first
    (tmp_path / "src/app.py").write_text("value = 2\n", encoding="utf-8")
    assert provenance.code_snapshot_sha256() != first
