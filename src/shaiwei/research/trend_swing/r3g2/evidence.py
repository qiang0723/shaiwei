"""Canonical write-once evidence primitives for isolated R3G-2 output mounts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.r3g2.contract import R3G2Error


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def write_once_bytes(path: Path, payload: bytes) -> tuple[str, bool]:
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if path.read_bytes() != payload:
            raise R3G2Error(f"R3G-2 write-once conflict: {path.name}")
        return digest, True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return digest, False


def write_once_json(path: Path, value: Any) -> tuple[str, bool]:
    return write_once_bytes(path, canonical_json(value) + b"\n")
