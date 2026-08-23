"""Strict loader for the central build-asset ownership registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml
from yaml.resolver import BaseResolver


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config/build_asset_registry_v1.yaml"
REGISTRY_SCHEMA = "shaiwei-build-asset-registry-v1"
_COMPONENT_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_TOP_LEVEL_KEYS = {"schema_version", "registry_id", "components"}
_COMPONENT_KEYS = {"id", "class", "status", "reuse_policy", "assets", "consumers"}


class BuildIdentityError(RuntimeError):
    """A build identity contract failed closed."""


class BuildAssetClass(StrEnum):
    GLOBAL = "GLOBAL"
    COMPONENT_RELEASE = "COMPONENT_RELEASE"
    FIXTURE_ONLY = "FIXTURE_ONLY"
    ARCHIVE_CANDIDATE = "ARCHIVE_CANDIDATE"


class ComponentStatus(StrEnum):
    ACTIVE_GLOBAL = "ACTIVE_GLOBAL"
    ACTIVE_LOCAL_READ_ONLY = "ACTIVE_LOCAL_READ_ONLY"
    CLOSED_FROZEN = "CLOSED_FROZEN"
    REVIEW_BEFORE_DELETE = "REVIEW_BEFORE_DELETE"


class ReusePolicy(StrEnum):
    GLOBAL_SNAPSHOT = "GLOBAL_SNAPSHOT"
    NEW_RELEASE_REQUIRED = "NEW_RELEASE_REQUIRED"
    FIXTURE_ONLY = "FIXTURE_ONLY"
    REVIEW_BEFORE_DELETE = "REVIEW_BEFORE_DELETE"


_VALID_POLICIES = {
    (BuildAssetClass.GLOBAL, ComponentStatus.ACTIVE_GLOBAL, ReusePolicy.GLOBAL_SNAPSHOT),
    (
        BuildAssetClass.COMPONENT_RELEASE,
        ComponentStatus.ACTIVE_LOCAL_READ_ONLY,
        ReusePolicy.NEW_RELEASE_REQUIRED,
    ),
    (
        BuildAssetClass.COMPONENT_RELEASE,
        ComponentStatus.CLOSED_FROZEN,
        ReusePolicy.NEW_RELEASE_REQUIRED,
    ),
    (BuildAssetClass.FIXTURE_ONLY, ComponentStatus.CLOSED_FROZEN, ReusePolicy.FIXTURE_ONLY),
    (
        BuildAssetClass.ARCHIVE_CANDIDATE,
        ComponentStatus.REVIEW_BEFORE_DELETE,
        ReusePolicy.REVIEW_BEFORE_DELETE,
    ),
}


@dataclass(frozen=True)
class BuildComponent:
    component_id: str
    asset_class: BuildAssetClass
    status: ComponentStatus
    reuse_policy: ReusePolicy
    assets: tuple[str, ...]
    consumers: tuple[str, ...]


@dataclass(frozen=True)
class BuildRegistry:
    schema_version: str
    registry_id: str
    registry_sha256: str
    components: tuple[BuildComponent, ...]

    def component(self, component_id: str) -> BuildComponent:
        matches = [item for item in self.components if item.component_id == component_id]
        if len(matches) != 1:
            raise BuildIdentityError(f"build component is not registered exactly once: {component_id}")
        return matches[0]

    @property
    def assets(self) -> tuple[str, ...]:
        return tuple(asset for component in self.components for asset in component.assets)


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise BuildIdentityError(f"build registry contains a duplicate key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def _canonical_sha256(document: object) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_exact_keys(document: dict[str, Any], expected: set[str], where: str) -> None:
    actual = set(document)
    if actual != expected:
        raise BuildIdentityError(
            f"{where} keys differ: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def _require_string_list(value: object, where: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise BuildIdentityError(f"{where} must be a list of strings")
    items = tuple(value)
    if not allow_empty and not items:
        raise BuildIdentityError(f"{where} must not be empty")
    if len(items) != len(set(items)):
        raise BuildIdentityError(f"{where} contains duplicate paths")
    if list(items) != sorted(items):
        raise BuildIdentityError(f"{where} paths are not canonical")
    return items


def _validate_relative_file(
    root: Path,
    relative: str,
    where: str,
    *,
    validate_filesystem: bool,
) -> None:
    path = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise BuildIdentityError(f"{where} is not a safe repository-relative path: {relative}")
    if not validate_filesystem:
        return
    candidate = root / path
    if not candidate.is_file() or candidate.is_symlink():
        raise BuildIdentityError(f"{where} is missing, not a file, or a symlink: {relative}")
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise BuildIdentityError(f"{where} escapes the project root: {relative}") from error


def _enum(enum_type: type[StrEnum], raw: object, where: str) -> StrEnum:
    if not isinstance(raw, str):
        raise BuildIdentityError(f"{where} must be a string")
    try:
        return enum_type(raw)
    except ValueError as error:
        raise BuildIdentityError(f"{where} is unknown: {raw}") from error


def _parse_component(
    raw: object,
    root: Path,
    *,
    validate_filesystem: bool,
) -> BuildComponent:
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise BuildIdentityError("build registry component must be a mapping with string keys")
    _require_exact_keys(raw, _COMPONENT_KEYS, "build registry component")
    component_id = raw["id"]
    if not isinstance(component_id, str) or not _COMPONENT_ID.fullmatch(component_id):
        raise BuildIdentityError(f"build component id is invalid: {component_id}")
    asset_class = _enum(BuildAssetClass, raw["class"], f"{component_id}.class")
    status = _enum(ComponentStatus, raw["status"], f"{component_id}.status")
    reuse_policy = _enum(ReusePolicy, raw["reuse_policy"], f"{component_id}.reuse_policy")
    policy = (asset_class, status, reuse_policy)
    if policy not in _VALID_POLICIES:
        raise BuildIdentityError(f"build component policy is incompatible: {component_id}")
    assets = _require_string_list(raw["assets"], f"{component_id}.assets")
    consumers = _require_string_list(raw["consumers"], f"{component_id}.consumers")
    for asset in assets:
        _validate_relative_file(
            root,
            asset,
            f"{component_id}.asset",
            validate_filesystem=validate_filesystem,
        )
    for consumer in consumers:
        _validate_relative_file(
            root,
            consumer,
            f"{component_id}.consumer",
            validate_filesystem=validate_filesystem,
        )
    return BuildComponent(
        component_id=component_id,
        asset_class=asset_class,
        status=status,
        reuse_policy=reuse_policy,
        assets=assets,
        consumers=consumers,
    )


def load_build_registry(
    path: Path | None = None,
    *,
    root: Path | None = None,
    validate_filesystem: bool = True,
) -> BuildRegistry:
    """Load and fully validate the build-asset ownership registry."""
    project_root = (root or PROJECT_ROOT).resolve()
    registry_path = path or project_root / "config/build_asset_registry_v1.yaml"
    try:
        document = yaml.load(registry_path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as error:
        raise BuildIdentityError("build registry is missing or invalid YAML") from error
    if not isinstance(document, dict) or any(not isinstance(key, str) for key in document):
        raise BuildIdentityError("build registry must be a mapping with string keys")
    _require_exact_keys(document, _TOP_LEVEL_KEYS, "build registry")
    if document["schema_version"] != REGISTRY_SCHEMA:
        raise BuildIdentityError("build registry schema is invalid")
    registry_id = document["registry_id"]
    if not isinstance(registry_id, str) or not _COMPONENT_ID.fullmatch(registry_id):
        raise BuildIdentityError("build registry id is invalid")
    raw_components = document["components"]
    if not isinstance(raw_components, list) or not raw_components:
        raise BuildIdentityError("build registry components must be a non-empty list")
    components = tuple(
        _parse_component(
            raw,
            project_root,
            validate_filesystem=validate_filesystem,
        )
        for raw in raw_components
    )
    component_ids = [item.component_id for item in components]
    if component_ids != sorted(component_ids) or len(component_ids) != len(set(component_ids)):
        raise BuildIdentityError("build registry component ids are not unique and canonical")
    assets = [asset for component in components for asset in component.assets]
    if len(assets) != len(set(assets)):
        raise BuildIdentityError("a build asset belongs to more than one component")
    if sum(item.asset_class is BuildAssetClass.GLOBAL for item in components) != 1:
        raise BuildIdentityError("build registry must contain exactly one GLOBAL component")
    return BuildRegistry(
        schema_version=REGISTRY_SCHEMA,
        registry_id=registry_id,
        registry_sha256=_canonical_sha256(document),
        components=components,
    )
