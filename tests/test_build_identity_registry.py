from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess

import pytest
import yaml

from shaiwei.build_identity.registry import (
    BuildAssetClass,
    BuildIdentityError,
    load_build_registry,
)
from shaiwei.build_identity.release import (
    ATTESTATION_SCHEMA,
    BUILD_SNAPSHOT_LABEL,
    REVISION_LABEL,
    SOURCE_BUNDLE_LABEL,
    canonical_attestation_sha256,
    component_build_snapshot_sha256,
    verify_component_release_attestation,
)
from shaiwei.provenance import CONTROLLED_FILES


ROOT = Path(__file__).parents[1]
REGISTRY_PATH = ROOT / "config/build_asset_registry_v1.yaml"


def _git_files(*pathspecs: str) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", *pathspecs],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def _web_attestation() -> tuple[dict[str, object], object]:
    registry = load_build_registry()
    component = registry.component("web-local")
    records = [
        {
            "path": relative,
            "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
        }
        for relative in component.assets
    ]
    build_snapshot = component_build_snapshot_sha256(records)
    source_bundle = "b" * 64
    revision = "a" * 40
    document: dict[str, object] = {
        "schema_version": ATTESTATION_SCHEMA,
        "attestation_sha256": "",
        "component_id": component.component_id,
        "registry_id": registry.registry_id,
        "registry_schema_version": registry.schema_version,
        "registry_sha256": registry.registry_sha256,
        "build_assets": records,
        "component_build_snapshot_sha256": build_snapshot,
        "source_bundle_sha256": source_bundle,
        "source_file_count": 27,
        "git_commit": revision,
        "origin_main": revision,
        "image_reference": "shaiwei:web-local-test",
        "image_id": f"sha256:{'c' * 64}",
        "labels": {
            REVISION_LABEL: revision,
            BUILD_SNAPSHOT_LABEL: build_snapshot,
            SOURCE_BUNDLE_LABEL: source_bundle,
        },
        "production_authorization": "none",
    }
    document["attestation_sha256"] = canonical_attestation_sha256(document)
    return document, registry


def _rehash(document: dict[str, object]) -> dict[str, object]:
    document["attestation_sha256"] = canonical_attestation_sha256(document)
    return document


def _write_registry(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_registry_covers_every_tracked_build_asset_exactly_once() -> None:
    registry = load_build_registry()
    tracked_build_assets = _git_files("Dockerfile*", "compose*.yaml")
    tracked_files = _git_files("*")

    assert len(tracked_build_assets) == 94
    assert len(registry.assets) == len(set(registry.assets)) == 94
    assert set(registry.assets) == tracked_build_assets
    assert {
        BuildAssetClass.GLOBAL,
        BuildAssetClass.COMPONENT_RELEASE,
        BuildAssetClass.FIXTURE_ONLY,
        BuildAssetClass.ARCHIVE_CANDIDATE,
    } == {component.asset_class for component in registry.components}
    assert all(set(component.consumers) <= tracked_files for component in registry.components)


def test_global_registry_matches_provenance_and_base_dockerfile_copy() -> None:
    registry = load_build_registry()
    tracked_build_assets = _git_files("Dockerfile*", "compose*.yaml")
    global_assets = set(registry.component("global-production").assets)
    assert global_assets == CONTROLLED_FILES & tracked_build_assets

    copied_files: set[str] = set()
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        if line.startswith("COPY "):
            copied_files.update(
                token for token in line.split()[1:-1] if (ROOT / token).is_file()
            )
    existing_controlled_files = {relative for relative in CONTROLLED_FILES if (ROOT / relative).is_file()}
    assert copied_files == existing_controlled_files


def test_component_boundaries_lock_web_m7_fixture_and_archive() -> None:
    registry = load_build_registry()
    assert registry.component("web-local").assets == (
        "Dockerfile.control",
        "Dockerfile.web",
        "compose.web.yaml",
    )
    assert "Dockerfile.m7-moneyflow-recovery-network.dockerignore" in registry.component(
        "m7-moneyflow"
    ).assets
    assert registry.component("m6-head30-500k-fixture").asset_class is BuildAssetClass.FIXTURE_ONLY
    assert registry.component("archive-candidates").assets == (
        "Dockerfile.star200-recovery",
        "Dockerfile.web-test",
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.update({"unexpected": True}), "keys differ"),
        (
            lambda doc: doc["components"][1]["assets"].append(
                doc["components"][0]["assets"][0]
            ),
            "paths are not canonical|more than one component",
        ),
        (
            lambda doc: doc["components"][0]["assets"].__setitem__(0, "../Dockerfile"),
            "safe repository-relative path",
        ),
        (
            lambda doc: doc["components"][0].update({"status": "ACTIVE_GLOBAL"}),
            "policy is incompatible",
        ),
    ],
)
def test_registry_rejects_schema_ownership_path_and_policy_drift(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    document = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    mutation(document)
    with pytest.raises(BuildIdentityError, match=message):
        load_build_registry(_write_registry(tmp_path, document), root=ROOT)


def test_registry_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(
        "schema_version: shaiwei-build-asset-registry-v1\n"
        "schema_version: duplicate\n"
        "registry_id: duplicate-test\n"
        "components: []\n",
        encoding="utf-8",
    )
    with pytest.raises(BuildIdentityError, match="duplicate key"):
        load_build_registry(path, root=ROOT)


def test_registry_metadata_mode_keeps_schema_and_path_safety_without_assets(
    tmp_path: Path,
) -> None:
    document = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    path = _write_registry(tmp_path, document)

    registry = load_build_registry(path, root=tmp_path, validate_filesystem=False)
    assert registry.component("m6-head30-delisting-risk-release").assets == (
        "Dockerfile.m6-head30-delisting-risk-release",
        "Dockerfile.m6-head30-delisting-risk-release.dockerignore",
        "compose.m6-head30-delisting-risk-release.yaml",
    )
    with pytest.raises(BuildIdentityError, match="missing, not a file"):
        load_build_registry(path, root=tmp_path)

    document["components"][0]["assets"][0] = "../Dockerfile"
    unsafe = _write_registry(tmp_path, document)
    with pytest.raises(BuildIdentityError, match="safe repository-relative path"):
        load_build_registry(unsafe, root=tmp_path, validate_filesystem=False)


def test_active_web_attestation_verifies_without_execution_authority() -> None:
    document, registry = _web_attestation()
    result = verify_component_release_attestation(document, registry)

    assert result["component_id"] == "web-local"
    assert result["release_identity_sha256"] == document["attestation_sha256"]
    assert result["production_authorization"] == "none"
    assert result["execution_authorized"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.pop("image_id"), "keys differ"),
        (lambda doc: doc.update({"unexpected": True}), "keys differ"),
        (
            lambda doc: doc["build_assets"].pop(),
            "build assets differ",
        ),
        (
            lambda doc: doc["build_assets"][0].update({"sha256": "d" * 64}),
            "build assets differ",
        ),
        (
            lambda doc: doc.update({"component_build_snapshot_sha256": "d" * 64}),
            "build snapshot differs",
        ),
        (lambda doc: doc.update({"origin_main": "d" * 40}), "not synchronized"),
        (lambda doc: doc.update({"image_id": "latest"}), "not content addressed"),
        (
            lambda doc: doc["labels"].update({REVISION_LABEL: "d" * 40}),
            "image labels differ",
        ),
        (
            lambda doc: doc["labels"].update({SOURCE_BUNDLE_LABEL: "d" * 64}),
            "image labels differ",
        ),
        (
            lambda doc: doc.update({"production_authorization": "production"}),
            "must not grant production authority",
        ),
    ],
)
def test_attestation_rejects_missing_extra_tampered_and_authority_drift(
    mutation,
    message: str,
) -> None:
    original, registry = _web_attestation()
    document = deepcopy(original)
    mutation(document)
    _rehash(document)

    with pytest.raises(BuildIdentityError, match=message):
        verify_component_release_attestation(document, registry)


@pytest.mark.parametrize(
    "component_id",
    [
        "global-production",
        "m5-dynamic",
        "m6-head30-500k-fixture",
        "archive-candidates",
    ],
)
def test_non_active_components_cannot_form_a_new_release(component_id: str) -> None:
    document, registry = _web_attestation()
    document["component_id"] = component_id
    _rehash(document)

    with pytest.raises(BuildIdentityError, match="not authorized to form a new active release"):
        verify_component_release_attestation(document, registry)


def test_attestation_self_identity_rejects_old_scope_reuse_after_change() -> None:
    document, registry = _web_attestation()
    document["image_reference"] = "shaiwei:web-local-different"

    with pytest.raises(BuildIdentityError, match="attestation identity differs"):
        verify_component_release_attestation(document, registry)


def test_attestation_rejects_non_string_top_level_keys() -> None:
    document, registry = _web_attestation()
    document[1] = "unexpected"

    with pytest.raises(BuildIdentityError, match="keys must be strings"):
        verify_component_release_attestation(document, registry)
