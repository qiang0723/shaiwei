"""Content-addressed source manifests embedded in component images."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping

from shaiwei.build_identity.registry import BuildIdentityError
from shaiwei.build_identity.release import component_build_snapshot_sha256


SOURCE_MANIFEST_SCHEMA = "shaiwei-component-source-manifest-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_KEYS = {
    "schema_version",
    "manifest_sha256",
    "git_commit",
    "source_bundle_sha256",
    "source_file_count",
    "files",
}
_FILE_KEYS = {"path", "sha256"}


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise BuildIdentityError("source manifest is not canonical JSON") from error


def canonical_source_manifest_sha256(document: Mapping[str, object]) -> str:
    unsigned = {key: value for key, value in document.items() if key != "manifest_sha256"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise BuildIdentityError(f"source path is not repository-relative: {relative}")
    candidate = root / path
    if not candidate.is_file() or candidate.is_symlink():
        raise BuildIdentityError(f"source file is missing, not regular, or a symlink: {relative}")
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise BuildIdentityError(f"source path escapes project root: {relative}") from error
    return candidate


def source_records(root: Path, names: list[str]) -> list[dict[str, str]]:
    if not names or names != sorted(names) or len(names) != len(set(names)):
        raise BuildIdentityError("source file names must be non-empty, unique, and canonical")
    return [
        {"path": name, "sha256": hashlib.sha256(_safe_file(root, name).read_bytes()).hexdigest()}
        for name in names
    ]


def build_source_manifest(root: Path, names: list[str], git_commit: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", git_commit) is None:
        raise BuildIdentityError("source manifest Git commit is invalid")
    files = source_records(root, names)
    document: dict[str, object] = {
        "schema_version": SOURCE_MANIFEST_SCHEMA,
        "manifest_sha256": "",
        "git_commit": git_commit,
        "source_bundle_sha256": component_build_snapshot_sha256(files),
        "source_file_count": len(files),
        "files": files,
    }
    document["manifest_sha256"] = canonical_source_manifest_sha256(document)
    return document


def _validated_records(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise BuildIdentityError("source manifest files must be a non-empty list")
    records: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != _FILE_KEYS:
            raise BuildIdentityError("source manifest file record schema differs")
        path, digest = item.get("path"), item.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise BuildIdentityError("source manifest file record is invalid")
        records.append({"path": path, "sha256": digest})
    paths = [record["path"] for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise BuildIdentityError("source manifest file records are not unique and canonical")
    return records


def verify_source_manifest(
    document: Mapping[str, object],
    *,
    root: Path | None = None,
) -> dict[str, object]:
    """Verify manifest identity and optionally every source file on the host."""
    if any(not isinstance(key, str) for key in document) or set(document) != _MANIFEST_KEYS:
        raise BuildIdentityError("source manifest schema differs")
    if document.get("schema_version") != SOURCE_MANIFEST_SCHEMA:
        raise BuildIdentityError("source manifest version differs")
    manifest_sha = document.get("manifest_sha256")
    if not isinstance(manifest_sha, str) or not _SHA256.fullmatch(manifest_sha):
        raise BuildIdentityError("source manifest SHA-256 is invalid")
    if canonical_source_manifest_sha256(document) != manifest_sha:
        raise BuildIdentityError("source manifest identity differs")
    git_commit = document.get("git_commit")
    if not isinstance(git_commit, str) or re.fullmatch(r"[0-9a-f]{40}", git_commit) is None:
        raise BuildIdentityError("source manifest Git identity is invalid")
    records = _validated_records(document.get("files"))
    if document.get("source_file_count") != len(records):
        raise BuildIdentityError("source manifest file count differs")
    bundle_sha = component_build_snapshot_sha256(records)
    if document.get("source_bundle_sha256") != bundle_sha:
        raise BuildIdentityError("source bundle identity differs")
    if root is not None and source_records(root.resolve(), [row["path"] for row in records]) != records:
        raise BuildIdentityError("source tree differs from embedded manifest")
    return {
        "manifest_sha256": manifest_sha,
        "git_commit": git_commit,
        "source_bundle_sha256": bundle_sha,
        "source_file_count": len(records),
    }
