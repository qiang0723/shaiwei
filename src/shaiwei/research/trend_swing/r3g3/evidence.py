"""Canonical write-once evidence primitives for R3G-3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class R3G3Error(RuntimeError):
    """Fail-closed R3G-3 contract violation."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once_bytes(path: Path, payload: bytes) -> str:
    if path.exists():
        raise R3G3Error(f"R3G-3 output already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def write_once_json(path: Path, value: Any) -> str:
    return write_once_bytes(path, canonical_json(value) + b"\n")


def file_manifest(root: Path) -> dict[str, Any]:
    files: Mapping[str, str] = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    return {
        "schema_version": "ts-v5-r3g3-diagnostic-manifest-v1",
        "file_count": len(files),
        "files": dict(files),
        "bundle_sha256": canonical_sha256(dict(files)),
    }

