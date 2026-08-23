"""Strict local Web component release configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath

from shaiwei.build_identity.multi_image_release import ImageReleaseSpec
from shaiwei.build_identity.registry import BuildIdentityError, PROJECT_ROOT


WEB_RELEASE_CONFIG_SCHEMA = "shaiwei-web-component-release-config-v2"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config/web_component_release_v2.json"
_CONFIG_KEYS = {
    "schema_version",
    "component_id",
    "compose_path",
    "embedded_manifest_build_path",
    "embedded_manifest_container_path",
    "source_roots",
    "source_files",
    "images",
    "candidate_path",
    "state_path",
    "audit_path",
    "ui_base_url",
}
_IMAGE_KEYS = {"role", "dockerfile", "repository", "services"}


class WebReleaseError(BuildIdentityError):
    """Fail-closed error shared by Web release adapters and orchestration."""


@dataclass(frozen=True)
class WebReleaseConfig:
    component_id: str
    compose_path: str
    embedded_manifest_build_path: str
    embedded_manifest_container_path: str
    source_roots: tuple[str, ...]
    source_files: tuple[str, ...]
    images: tuple[ImageReleaseSpec, ...]
    candidate_path: str
    state_path: str
    audit_path: str
    ui_base_url: str


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise BuildIdentityError(f"Web release config contains duplicate key: {key}")
        document[key] = value
    return document


def _safe_relative(root: Path, value: object, where: str, *, require_file: bool) -> str:
    if not isinstance(value, str):
        raise BuildIdentityError(f"{where} must be a string")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise BuildIdentityError(f"{where} is not a safe project-relative path")
    target = root / path
    if require_file and (not target.is_file() or target.is_symlink()):
        raise BuildIdentityError(f"{where} is missing, not regular, or a symlink: {value}")
    return value


def _sorted_strings(raw: object, where: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw or any(not isinstance(item, str) for item in raw):
        raise BuildIdentityError(f"{where} must be a non-empty string list")
    values = tuple(raw)
    if list(values) != sorted(values) or len(values) != len(set(values)):
        raise BuildIdentityError(f"{where} must be unique and canonical")
    return values


def _image_specs(root: Path, raw: object) -> tuple[ImageReleaseSpec, ...]:
    if not isinstance(raw, list):
        raise BuildIdentityError("Web release images must be a list")
    specs: list[ImageReleaseSpec] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != _IMAGE_KEYS:
            raise BuildIdentityError("Web release image config schema differs")
        role, repository = item.get("role"), item.get("repository")
        if not isinstance(role, str) or not isinstance(repository, str) or not repository:
            raise BuildIdentityError("Web release image role or repository is invalid")
        dockerfile = _safe_relative(root, item.get("dockerfile"), f"{role}.dockerfile", require_file=True)
        services = _sorted_strings(item.get("services"), f"{role}.services")
        specs.append(ImageReleaseSpec(role, dockerfile, repository, services))
    result = tuple(specs)
    if [spec.role for spec in result] != ["research-control", "web-runtime"]:
        raise BuildIdentityError("Web release must declare the two frozen image roles")
    expected = {
        "research-control": ("Dockerfile.control", ("research-control",)),
        "web-runtime": ("Dockerfile.web", ("web-query", "web-ui")),
    }
    if any((spec.dockerfile, spec.services) != expected[spec.role] for spec in result):
        raise BuildIdentityError("Web release image role, Dockerfile, or services differ")
    return result


def load_web_release_config(
    path: Path | None = None,
    *,
    root: Path | None = None,
) -> WebReleaseConfig:
    project_root = (root or PROJECT_ROOT).resolve()
    config_path = path or project_root / "config/web_component_release_v2.json"
    try:
        document = json.loads(
            config_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, json.JSONDecodeError) as error:
        raise BuildIdentityError("Web release config is missing or invalid JSON") from error
    if not isinstance(document, dict) or set(document) != _CONFIG_KEYS:
        raise BuildIdentityError("Web release config schema differs")
    if document.get("schema_version") != WEB_RELEASE_CONFIG_SCHEMA:
        raise BuildIdentityError("Web release config version differs")
    if document.get("component_id") != "web-local":
        raise BuildIdentityError("Web release component id differs")
    compose_path = _safe_relative(
        project_root, document.get("compose_path"), "compose_path", require_file=True
    )
    manifest_build_path = _safe_relative(
        project_root,
        document.get("embedded_manifest_build_path"),
        "embedded_manifest_build_path",
        require_file=False,
    )
    container_path = document.get("embedded_manifest_container_path")
    if container_path != "/opt/shaiwei/component-source-manifest.json":
        raise BuildIdentityError("Web release embedded container manifest path differs")
    source_roots = _sorted_strings(document.get("source_roots"), "source_roots")
    for source_root in source_roots:
        relative = _safe_relative(project_root, source_root, "source_root", require_file=False)
        if not (project_root / relative).is_dir():
            raise BuildIdentityError(f"Web release source root is not a directory: {relative}")
    source_files = _sorted_strings(document.get("source_files"), "source_files")
    for source_file in source_files:
        _safe_relative(project_root, source_file, "source_file", require_file=True)
    candidate_path = _safe_relative(
        project_root, document.get("candidate_path"), "candidate_path", require_file=False
    )
    state_path = _safe_relative(
        project_root, document.get("state_path"), "state_path", require_file=False
    )
    audit_path = _safe_relative(
        project_root, document.get("audit_path"), "audit_path", require_file=False
    )
    if document.get("ui_base_url") != "http://127.0.0.1:8080":
        raise BuildIdentityError("Web release UI base URL must remain loopback-only")
    return WebReleaseConfig(
        component_id="web-local",
        compose_path=compose_path,
        embedded_manifest_build_path=manifest_build_path,
        embedded_manifest_container_path=str(container_path),
        source_roots=source_roots,
        source_files=source_files,
        images=_image_specs(project_root, document.get("images")),
        candidate_path=candidate_path,
        state_path=state_path,
        audit_path=audit_path,
        ui_base_url=str(document["ui_base_url"]),
    )
