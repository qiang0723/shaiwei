"""Small immutable-artifact helpers owned by F1-1."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.ledger import sha256_file


class ImmutableArtifactError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def json_payload(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json_once(path: Path, value: dict[str, object]) -> tuple[Path, str, bool]:
    payload = json_payload(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise ImmutableArtifactError(f"existing immutable JSON differs: {path}")
        return path, sha256_file(path), True
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path, sha256_file(path), False


def write_content_addressed_parquet(
    frame: pd.DataFrame,
    directory: Path,
    *,
    stem: str,
) -> tuple[Path, str, bool]:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".{stem}.{uuid.uuid4().hex}.tmp.parquet"
    try:
        frame.to_parquet(temporary, index=False, compression="zstd")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        content_hash = sha256_file(temporary)
        target = directory / f"{stem}-{content_hash[:16]}.parquet"
        if target.is_file():
            if sha256_file(target) != content_hash:
                raise ImmutableArtifactError(f"content-addressed artifact differs: {target}")
            return target, content_hash, True
        os.link(temporary, target)
        return target, content_hash, False
    finally:
        temporary.unlink(missing_ok=True)
