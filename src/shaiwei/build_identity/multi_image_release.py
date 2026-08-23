"""Versioned multi-image component release attestation verification."""

from __future__ import annotations

from dataclasses import dataclass
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
from shaiwei.build_identity.release import (
    BUILD_SNAPSHOT_LABEL,
    REVISION_LABEL,
    SOURCE_BUNDLE_LABEL,
    component_asset_records,
    component_build_snapshot_sha256,
)
from shaiwei.build_identity.source_bundle import verify_source_manifest


MULTI_IMAGE_ATTESTATION_SCHEMA = "shaiwei-component-release-attestation-v2"
MULTI_IMAGE_VERIFICATION_SCHEMA = "shaiwei-component-release-verification-v2"
IMAGE_ROLE_LABEL = "io.shaiwei.component_image_role"
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
    "source_manifest_sha256",
    "source_bundle_sha256",
    "source_file_count",
    "git_commit",
    "origin_main",
    "images",
    "production_authorization",
}
_IMAGE_KEYS = {
    "role",
    "dockerfile",
    "services",
    "image_reference",
    "image_id",
    "labels",
    "embedded_manifest_sha256",
}
_LABEL_KEYS = {REVISION_LABEL, BUILD_SNAPSHOT_LABEL, SOURCE_BUNDLE_LABEL, IMAGE_ROLE_LABEL}


@dataclass(frozen=True)
class ImageReleaseSpec:
    role: str
    dockerfile: str
    repository: str
    services: tuple[str, ...]


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise BuildIdentityError("multi-image attestation is not canonical JSON") from error


def canonical_multi_image_attestation_sha256(document: Mapping[str, object]) -> str:
    unsigned = {key: value for key, value in document.items() if key != "attestation_sha256"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _exact_keys(document: Mapping[str, object], expected: set[str], where: str) -> None:
    if any(not isinstance(key, str) for key in document) or set(document) != expected:
        raise BuildIdentityError(f"{where} schema differs")


def _string(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise BuildIdentityError(f"multi-image attestation {key} must be a non-empty string")
    return value


def _asset_records(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise BuildIdentityError("multi-image build assets must be a non-empty list")
    records: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise BuildIdentityError("multi-image build asset record schema differs")
        path, digest = item.get("path"), item.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise BuildIdentityError("multi-image build asset record is invalid")
        records.append({"path": path, "sha256": digest})
    paths = [record["path"] for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise BuildIdentityError("multi-image build assets are not unique and canonical")
    return records


def _validated_specs(specs: tuple[ImageReleaseSpec, ...]) -> dict[str, ImageReleaseSpec]:
    roles = [spec.role for spec in specs]
    if not roles or roles != sorted(roles) or len(roles) != len(set(roles)):
        raise BuildIdentityError("image release specs are not unique and canonical")
    for spec in specs:
        if (
            re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", spec.role) is None
            or not spec.dockerfile
            or not spec.repository
            or not spec.services
            or list(spec.services) != sorted(spec.services)
            or len(spec.services) != len(set(spec.services))
        ):
            raise BuildIdentityError(f"image release spec is invalid: {spec.role}")
    return {spec.role: spec for spec in specs}


def _validate_image(
    raw: object,
    spec: ImageReleaseSpec,
    *,
    revision: str,
    build_snapshot: str,
    source_bundle: str,
    source_manifest: str,
) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise BuildIdentityError("multi-image image record must be a mapping")
    _exact_keys(raw, _IMAGE_KEYS, "multi-image image record")
    if raw.get("role") != spec.role or raw.get("dockerfile") != spec.dockerfile:
        raise BuildIdentityError(f"image role or Dockerfile differs: {spec.role}")
    services = raw.get("services")
    if not isinstance(services, list) or tuple(services) != spec.services:
        raise BuildIdentityError(f"image service coverage differs: {spec.role}")
    image_reference = raw.get("image_reference")
    if (
        not isinstance(image_reference, str)
        or not image_reference.startswith(f"{spec.repository}-")
        or image_reference.strip() != image_reference
        or any(char.isspace() for char in image_reference)
    ):
        raise BuildIdentityError(f"image reference differs from registered repository: {spec.role}")
    image_id = raw.get("image_id")
    if not isinstance(image_id, str) or not _IMAGE_ID.fullmatch(image_id):
        raise BuildIdentityError(f"image id is not content addressed: {spec.role}")
    if raw.get("embedded_manifest_sha256") != source_manifest:
        raise BuildIdentityError(f"embedded source manifest differs: {spec.role}")
    labels = raw.get("labels")
    if not isinstance(labels, dict):
        raise BuildIdentityError(f"image labels must be a mapping: {spec.role}")
    _exact_keys(labels, _LABEL_KEYS, f"image labels for {spec.role}")
    expected_labels = {
        REVISION_LABEL: revision,
        BUILD_SNAPSHOT_LABEL: build_snapshot,
        SOURCE_BUNDLE_LABEL: source_bundle,
        IMAGE_ROLE_LABEL: spec.role,
    }
    if labels != expected_labels:
        raise BuildIdentityError(f"image labels differ: {spec.role}")
    return {
        "role": spec.role,
        "image_reference": image_reference,
        "image_id": image_id,
    }


def verify_multi_image_attestation(
    document: Mapping[str, object],
    registry: BuildRegistry,
    specs: tuple[ImageReleaseSpec, ...],
    source_manifest: Mapping[str, object],
    *,
    root: Path | None = None,
) -> dict[str, object]:
    """Verify all image roles for one component without granting runtime authority."""
    _exact_keys(document, _ATTESTATION_KEYS, "multi-image attestation")
    if document.get("schema_version") != MULTI_IMAGE_ATTESTATION_SCHEMA:
        raise BuildIdentityError("multi-image attestation version differs")
    attestation_sha = _string(document, "attestation_sha256")
    if not _SHA256.fullmatch(attestation_sha):
        raise BuildIdentityError("multi-image attestation SHA-256 is invalid")
    if canonical_multi_image_attestation_sha256(document) != attestation_sha:
        raise BuildIdentityError("multi-image attestation identity differs")

    component_id = _string(document, "component_id")
    component = registry.component(component_id)
    if (
        component.asset_class is not BuildAssetClass.COMPONENT_RELEASE
        or component.status is not ComponentStatus.ACTIVE_LOCAL_READ_ONLY
    ):
        raise BuildIdentityError("component is not authorized for an active multi-image release")
    if (
        document.get("registry_id") != registry.registry_id
        or document.get("registry_schema_version") != registry.schema_version
        or document.get("registry_sha256") != registry.registry_sha256
    ):
        raise BuildIdentityError("multi-image registry identity differs")

    project_root = (root or PROJECT_ROOT).resolve()
    expected_assets = component_asset_records(component.assets, project_root)
    actual_assets = _asset_records(document.get("build_assets"))
    if actual_assets != expected_assets:
        raise BuildIdentityError("multi-image build assets differ from registry or source tree")
    build_snapshot = component_build_snapshot_sha256(expected_assets)
    if document.get("component_build_snapshot_sha256") != build_snapshot:
        raise BuildIdentityError("multi-image build snapshot differs")

    manifest_identity = verify_source_manifest(source_manifest)
    if (
        document.get("source_manifest_sha256") != manifest_identity["manifest_sha256"]
        or document.get("source_bundle_sha256") != manifest_identity["source_bundle_sha256"]
        or document.get("source_file_count") != manifest_identity["source_file_count"]
    ):
        raise BuildIdentityError("multi-image source manifest identity differs")
    revision = _string(document, "git_commit")
    origin_main = _string(document, "origin_main")
    if not _GIT_COMMIT.fullmatch(revision) or revision != origin_main:
        raise BuildIdentityError("multi-image Git identity is invalid or not pushed")
    if manifest_identity["git_commit"] != revision:
        raise BuildIdentityError("multi-image source manifest Git identity differs")

    expected_specs = _validated_specs(specs)
    raw_images = document.get("images")
    if not isinstance(raw_images, list):
        raise BuildIdentityError("multi-image images must be a list")
    roles = [item.get("role") if isinstance(item, dict) else None for item in raw_images]
    if roles != sorted(expected_specs) or len(roles) != len(set(roles)):
        raise BuildIdentityError("multi-image roles are missing, extra, duplicate, or non-canonical")
    images = [
        _validate_image(
            raw,
            expected_specs[role],
            revision=revision,
            build_snapshot=build_snapshot,
            source_bundle=str(manifest_identity["source_bundle_sha256"]),
            source_manifest=str(manifest_identity["manifest_sha256"]),
        )
        for raw, role in zip(raw_images, roles, strict=True)
    ]
    if document.get("production_authorization") != "none":
        raise BuildIdentityError("multi-image attestation must not grant production authority")
    return {
        "schema_version": MULTI_IMAGE_VERIFICATION_SCHEMA,
        "component_id": component_id,
        "registry_sha256": registry.registry_sha256,
        "component_build_snapshot_sha256": build_snapshot,
        "source_manifest_sha256": manifest_identity["manifest_sha256"],
        "source_bundle_sha256": manifest_identity["source_bundle_sha256"],
        "git_commit": revision,
        "images": images,
        "release_identity_sha256": attestation_sha,
        "production_authorization": "none",
        "execution_authorized": False,
    }
