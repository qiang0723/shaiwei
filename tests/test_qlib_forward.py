import json
import os
from pathlib import Path

from shaiwei.config import load
from shaiwei.transform.qlib_bin import QLIB_MANIFEST, qlib_tree_integrity
from shaiwei.transform.qlib_forward import (
    ForwardSnapshot,
    _prune_versions,
    _write_pointer,
    current_forward_snapshot,
)


def _version(root: Path, name: str, data_hash: str, code_hash: str) -> tuple[Path, str]:
    version = root / "versions" / name
    feature = version / "features/sh600000/close.day.bin"
    feature.parent.mkdir(parents=True)
    feature.write_bytes(name.encode())
    integrity = qlib_tree_integrity(version)
    (version / QLIB_MANIFEST).write_text(
        json.dumps(
            {
                "data_snapshot_sha256": data_hash,
                "code_snapshot_sha256": code_hash,
                **integrity,
            }
        )
    )
    return version, str(integrity["artifact_sha256"])


def test_forward_pointer_is_verified_and_old_versions_are_pruned(tmp_path: Path):
    settings = load()
    settings.runtime.data_root = tmp_path
    root = tmp_path / "qlib_forward"
    old, _ = _version(root, "old", "a" * 64, "b" * 64)
    previous, _ = _version(root, "previous", "c" * 64, "d" * 64)
    current, artifact = _version(root, "current", "e" * 64, "f" * 64)
    os.utime(old, ns=(1, 1))
    os.utime(previous, ns=(2, 2))
    os.utime(current, ns=(3, 3))
    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text("{}")
    snapshot = ForwardSnapshot(current, "e" * 64, "f" * 64, artifact, sentinel)
    _write_pointer(root, snapshot)
    loaded = current_forward_snapshot(settings)
    assert loaded.provider_uri == current
    assert loaded.artifact_sha256 == artifact

    _prune_versions(root, current=current, keep=2)
    assert current.exists()
    assert previous.exists()
    assert not old.exists()
