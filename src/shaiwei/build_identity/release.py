"""Pure, fail-closed verification for component release attestations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Mapping

from shaiwei.build_identity.registry import (
    BuildAssetClass,
    BuildIdentityError,
    BuildRegistry,
    ComponentStatus,
    PROJECT_ROOT,
)


ATTESTATION_SCHEMA = "shaiwei-component-release-attestation-v1"
VERIFICATION_SCHEMA = "shaiwei-component-release-verification-v1"
REVISION_LABEL = "org.opencontainers.image.revision"
BUILD_SNAPSHOT_LABEL = "io.shaiwei.component_build_snapshot_sha256"
SOURCE_BUNDLE_LABEL = "io.shaiwei.source_bundle_sha256"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ATTESTATION_KEYS = {
    "schema_version",
    "attestation_sha256",
    "component_id",
    "registry_id",
    "registry_schema_version",
    "registry_sha256",
    "build_assets",
    "component_build_snapshot_sha256",
    "source_bundle_sha256",
    "source_file_count",
    "git_commit",
    "origin_main",
    "image_reference",
    "image_id",
    "labels",
    "production_authorization",
}
_ASSET_KEYS = {"path", "sha256"}
_LABEL_KEYS = {REVISION_LABEL, BUILD_SNAPSHOT_LABEL, SOURCE_BUNDLE_LABEL}


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise BuildIdentityError("component release attestation is not canonical JSON") from error


def canonical_attestation_sha256(document: Mapping[str, object]) -> str:
    """Hash an attestation without its self-referential digest field."""
    unsigned = {key: value for key, value in document.items() if key != "attestation_sha256"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _require_exact_keys(document: Mapping[str, object], expected: set[str], where: str) -> None:
    actual = set(document)
    if actual != expected:
        raise BuildIdentityError(
            f"{where} keys differ: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def _require_string(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise BuildIdentityError(f"component release {key} must be a non-empty string")
    return value


def component_asset_records(component_assets: tuple[str, ...], root: Path) -> list[dict[str, str]]:
    """Read canonical registered build-asset identities from one source tree."""
    records: list[dict[str, str]] = []
    for relative in component_assets:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise BuildIdentityError(f"registered build asset is unavailable: {relative}")
        records.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def component_build_snapshot_sha256(records: list[dict[str, str]]) -> str:
    """Build a deterministic path-and-content identity for one component."""
    if not records:
        raise BuildIdentityError("component build asset records must not be empty")
    paths: list[str] = []
    for record in records:
        _require_exact_keys(record, _ASSET_KEYS, "component build asset record")
        path = record.get("path")
        digest = record.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise BuildIdentityError("component build asset record is invalid")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise BuildIdentityError("component build asset records are not unique and canonical")
    payload = hashlib.sha256()
    for record in records:
        payload.update(record["path"].encode("utf-8"))
        payload.update(b"\0")
        payload.update(bytes.fromhex(record["sha256"]))
    return payload.hexdigest()


def _parse_asset_records(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise BuildIdentityError("component release build_assets must be a list")
    records: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or any(not isinstance(key, str) for key in item):
            raise BuildIdentityError("component release asset record must be a mapping")
        _require_exact_keys(item, _ASSET_KEYS, "component release asset record")
        path = item.get("path")
        digest = item.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise BuildIdentityError("component release asset record is invalid")
        records.append({"path": path, "sha256": digest})
    paths = [record["path"] for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise BuildIdentityError("component release asset records are not unique and canonical")
    return records


def _validate_labels(raw: object, *, revision: str, build: str, source: str) -> None:
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise BuildIdentityError("component release labels must be a mapping")
    _require_exact_keys(raw, _LABEL_KEYS, "component release labels")
    expected = {
        REVISION_LABEL: revision,
        BUILD_SNAPSHOT_LABEL: build,
        SOURCE_BUNDLE_LABEL: source,
    }
    if raw != expected:
        raise BuildIdentityError("component release image labels differ from the attested identity")


def verify_component_release_attestation(
    document: Mapping[str, object],
    registry: BuildRegistry,
    *,
    root: Path | None = None,
) -> dict[str, object]:
    """Verify one component release identity without granting execution authority."""
    if any(not isinstance(key, str) for key in document):
        raise BuildIdentityError("component release attestation keys must be strings")
    _require_exact_keys(document, _ATTESTATION_KEYS, "component release attestation")
    if document.get("schema_version") != ATTESTATION_SCHEMA:
        raise BuildIdentityError("component release attestation schema is invalid")
    attestation_sha = _require_string(document, "attestation_sha256")
    if not _SHA256.fullmatch(attestation_sha):
        raise BuildIdentityError("component release attestation SHA-256 is invalid")
    if canonical_attestation_sha256(document) != attestation_sha:
        raise BuildIdentityError("component release attestation identity differs")

    component_id = _require_string(document, "component_id")
    component = registry.component(component_id)
    if (
        component.asset_class is not BuildAssetClass.COMPONENT_RELEASE
        or component.status is not ComponentStatus.ACTIVE_LOCAL_READ_ONLY
    ):
        raise BuildIdentityError("component is not authorized to form a new active release")
    if document.get("registry_id") != registry.registry_id:
        raise BuildIdentityError("component release registry id differs")
    if document.get("registry_schema_version") != registry.schema_version:
        raise BuildIdentityError("component release registry schema differs")
    if document.get("registry_sha256") != registry.registry_sha256:
        raise BuildIdentityError("component release registry identity differs")

    project_root = (root or PROJECT_ROOT).resolve()
    expected_records = component_asset_records(component.assets, project_root)
    actual_records = _parse_asset_records(document.get("build_assets"))
    if actual_records != expected_records:
        raise BuildIdentityError("component release build assets differ from the registry or working tree")
    build_snapshot = component_build_snapshot_sha256(expected_records)
    if document.get("component_build_snapshot_sha256") != build_snapshot:
        raise BuildIdentityError("component release build snapshot differs")

    source_bundle = _require_string(document, "source_bundle_sha256")
    if not _SHA256.fullmatch(source_bundle):
        raise BuildIdentityError("component release source bundle SHA-256 is invalid")
    source_file_count = document.get("source_file_count")
    if isinstance(source_file_count, bool) or not isinstance(source_file_count, int):
        raise BuildIdentityError("component release source file count must be an integer")
    if source_file_count <= 0:
        raise BuildIdentityError("component release source file count must be positive")

    git_commit = _require_string(document, "git_commit")
    origin_main = _require_string(document, "origin_main")
    if not _GIT_COMMIT.fullmatch(git_commit) or not _GIT_COMMIT.fullmatch(origin_main):
        raise BuildIdentityError("component release Git identity is invalid")
    if git_commit != origin_main:
        raise BuildIdentityError("component release Git commit is not synchronized with origin/main")
    image_reference = _require_string(document, "image_reference")
    if image_reference.strip() != image_reference or any(char.isspace() for char in image_reference):
        raise BuildIdentityError("component release image reference is invalid")
    image_id = _require_string(document, "image_id")
    if not _IMAGE_ID.fullmatch(image_id):
        raise BuildIdentityError("component release image id is not content addressed")
    _validate_labels(
        document.get("labels"),
        revision=git_commit,
        build=build_snapshot,
        source=source_bundle,
    )
    if document.get("production_authorization") != "none":
        raise BuildIdentityError("component release must not grant production authority")

    return {
        "schema_version": VERIFICATION_SCHEMA,
        "component_id": component_id,
        "registry_sha256": registry.registry_sha256,
        "component_build_snapshot_sha256": build_snapshot,
        "source_bundle_sha256": source_bundle,
        "git_commit": git_commit,
        "image_reference": image_reference,
        "image_id": image_id,
        "release_identity_sha256": attestation_sha,
        "production_authorization": "none",
        "execution_authorized": False,
    }
