"""Canonical write-once artifacts for M6-3B synthetic engineering."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shaiwei.research.topk_conversion.contract import ConversionError


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConversionError("M6-3 artifact is not canonical JSON") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def write_once_json(path: Path, value: Any) -> tuple[str, bool]:
    payload = canonical_json(value) + b"\n"
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if path.read_bytes() != payload:
            raise ConversionError(f"M6-3 write-once conflict: {path.name}")
        return digest, True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return digest, False


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConversionError(f"M6-3 artifact cannot be read: {path.name}") from exc
    if not isinstance(value, dict):
        raise ConversionError(f"M6-3 artifact is not a mapping: {path.name}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
