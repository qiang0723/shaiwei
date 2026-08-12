from pathlib import Path

import pytest

from shaiwei.research.trend_swing.contract import TrendSwingError
from shaiwei.research.trend_swing.recovery_release import write_release_once


def test_release_write_is_create_once(monkeypatch, tmp_path: Path):
    document = {
        "schema_version": "ts-v3-data-recovery-release-v1",
        "release_scope_sha256": "a" * 64,
        "execution_authorized": False,
        "scope": {},
    }
    monkeypatch.setattr(
        "shaiwei.research.trend_swing.recovery_release.build_release_document",
        lambda: document,
    )
    path = tmp_path / "release.yaml"
    assert write_release_once(path) == document
    with pytest.raises(TrendSwingError, match="already exists"):
        write_release_once(path)
