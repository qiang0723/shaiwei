from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.build_identity.multi_image_release import (
    BUILD_SNAPSHOT_LABEL,
    IMAGE_ROLE_LABEL,
    MULTI_IMAGE_ATTESTATION_SCHEMA,
    REVISION_LABEL,
    SOURCE_BUNDLE_LABEL,
    canonical_multi_image_attestation_sha256,
    verify_multi_image_attestation,
)
from shaiwei.build_identity.registry import BuildIdentityError, load_build_registry
from shaiwei.build_identity.release import (
    component_asset_records,
    component_build_snapshot_sha256,
)
from shaiwei.build_identity.source_bundle import (
    build_source_manifest,
    source_records,
    verify_source_manifest,
)
from shaiwei.build_identity.web_release_config import load_web_release_config


ROOT = Path(__file__).parents[1]
REVISION = "a" * 40


def _attestation() -> tuple[dict[str, object], object, tuple[object, ...], dict[str, object]]:
    registry = load_build_registry()
    config = load_web_release_config()
    component = registry.component(config.component_id)
    assets = component_asset_records(component.assets, ROOT)
    build_snapshot = component_build_snapshot_sha256(assets)
    manifest = build_source_manifest(ROOT, ["pyproject.toml"], REVISION)
    images = []
    for index, spec in enumerate(config.images, start=1):
        images.append(
            {
                "role": spec.role,
                "dockerfile": spec.dockerfile,
                "services": list(spec.services),
                "image_reference": f"{spec.repository}-fixture",
                "image_id": f"sha256:{str(index) * 64}",
                "labels": {
                    REVISION_LABEL: REVISION,
                    BUILD_SNAPSHOT_LABEL: build_snapshot,
                    SOURCE_BUNDLE_LABEL: manifest["source_bundle_sha256"],
                    IMAGE_ROLE_LABEL: spec.role,
                },
                "embedded_manifest_sha256": manifest["manifest_sha256"],
            }
        )
    document: dict[str, object] = {
        "schema_version": MULTI_IMAGE_ATTESTATION_SCHEMA,
        "attestation_sha256": "",
        "component_id": component.component_id,
        "registry_id": registry.registry_id,
        "registry_schema_version": registry.schema_version,
        "registry_sha256": registry.registry_sha256,
        "build_assets": assets,
        "component_build_snapshot_sha256": build_snapshot,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_bundle_sha256": manifest["source_bundle_sha256"],
        "source_file_count": manifest["source_file_count"],
        "git_commit": REVISION,
        "origin_main": REVISION,
        "images": images,
        "production_authorization": "none",
    }
    document["attestation_sha256"] = canonical_multi_image_attestation_sha256(document)
    return document, registry, config.images, manifest


def _rehash(document: dict[str, object]) -> None:
    document["attestation_sha256"] = canonical_multi_image_attestation_sha256(document)


def test_source_manifest_is_deterministic_and_host_verified(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta\n", encoding="utf-8")
    names = ["a.txt", "b.txt"]

    first = build_source_manifest(tmp_path, names, REVISION)
    second = build_source_manifest(tmp_path, names, REVISION)

    assert first == second
    assert first["source_file_count"] == 2
    assert verify_source_manifest(first, root=tmp_path)["source_bundle_sha256"] == first[
        "source_bundle_sha256"
    ]

    (tmp_path / "b.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(BuildIdentityError, match="source tree differs"):
        verify_source_manifest(first, root=tmp_path)


def test_source_manifest_rejects_noncanonical_and_escaping_paths(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    with pytest.raises(BuildIdentityError, match="unique, and canonical"):
        build_source_manifest(tmp_path, ["a.txt", "a.txt"], REVISION)
    with pytest.raises(BuildIdentityError, match="repository-relative"):
        source_records(tmp_path, ["../a.txt"])


def test_multi_image_attestation_verifies_both_roles_without_authority() -> None:
    document, registry, specs, manifest = _attestation()

    result = verify_multi_image_attestation(document, registry, specs, manifest, root=ROOT)

    assert [row["role"] for row in result["images"]] == ["research-control", "web-runtime"]
    assert result["execution_authorized"] is False
    assert result["production_authorization"] == "none"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc["images"].pop(), "roles are missing"),
        (
            lambda doc: doc["images"][1].update({"role": "research-control"}),
            "roles are missing",
        ),
        (
            lambda doc: doc["images"][0].update({"dockerfile": "Dockerfile.web"}),
            "role or Dockerfile differs",
        ),
        (
            lambda doc: doc["images"][1].update({"services": ["web-ui"]}),
            "service coverage differs",
        ),
        (
            lambda doc: doc["images"][0]["labels"].update({IMAGE_ROLE_LABEL: "web-runtime"}),
            "labels differ",
        ),
        (
            lambda doc: doc["images"][0].update({"embedded_manifest_sha256": "d" * 64}),
            "embedded source manifest differs",
        ),
        (
            lambda doc: doc["images"][0].update({"image_id": "legacy:latest"}),
            "not content addressed",
        ),
        (
            lambda doc: doc.update({"component_build_snapshot_sha256": "d" * 64}),
            "build snapshot differs",
        ),
        (
            lambda doc: doc.update({"origin_main": "b" * 40}),
            "not pushed",
        ),
        (
            lambda doc: doc.update({"production_authorization": "production"}),
            "must not grant production authority",
        ),
    ],
)
def test_multi_image_attestation_fails_closed_on_role_identity_and_authority_drift(
    mutation,
    message: str,
) -> None:
    original, registry, specs, manifest = _attestation()
    document = deepcopy(original)
    mutation(document)
    _rehash(document)

    with pytest.raises(BuildIdentityError, match=message):
        verify_multi_image_attestation(document, registry, specs, manifest, root=ROOT)


def test_multi_image_attestation_self_hash_rejects_unrehashable_change() -> None:
    document, registry, specs, manifest = _attestation()
    document["images"][0]["image_reference"] = "shaiwei:changed"

    with pytest.raises(BuildIdentityError, match="attestation identity differs"):
        verify_multi_image_attestation(document, registry, specs, manifest, root=ROOT)


def test_web_release_config_and_build_files_freeze_dual_image_boundary() -> None:
    config = load_web_release_config()
    assert [spec.role for spec in config.images] == ["research-control", "web-runtime"]
    assert config.ui_base_url == "http://127.0.0.1:8080"
    assert config.embedded_manifest_build_path == ".web-release/component-source-manifest.json"

    for dockerfile, role in (("Dockerfile.control", "research-control"), ("Dockerfile.web", "web-runtime")):
        text = (ROOT / dockerfile).read_text(encoding="utf-8")
        assert 'org.opencontainers.image.revision="${SHAIWEI_COMPONENT_GIT_COMMIT}"' in text
        assert "io.shaiwei.component_build_snapshot_sha256" in text
        assert "io.shaiwei.source_bundle_sha256" in text
        assert f'ARG SHAIWEI_COMPONENT_IMAGE_ROLE="{role}"' in text
        assert "COPY .web-release/component-source-manifest.json" in text

    compose = yaml.safe_load((ROOT / "compose.web.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["web-query"]["image"].startswith("${SHAIWEI_WEB_RUNTIME_IMAGE:")
    assert services["web-ui"]["image"].startswith("${SHAIWEI_WEB_RUNTIME_IMAGE:")
    assert services["research-control"]["image"].startswith("${SHAIWEI_WEB_CONTROL_IMAGE:")
    assert services["web-ui"]["ports"] == ["127.0.0.1:8080:8080"]

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "docker-web-release-promote:" in makefile
    assert "docker-web-release-prepare-successor:" in makefile
    assert "-m shaiwei.build_identity.web_release prepare-successor" in makefile
    assert makefile.count("-m shaiwei.build_identity.web_release build") == 2
    assert "-m shaiwei.build_identity.web_release start" in makefile
    assert "-m shaiwei.build_identity.web_release status" in makefile


def test_source_manifest_hash_is_sensitive_to_path_and_content(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"same")
    (tmp_path / "b").write_bytes(b"same")
    a = build_source_manifest(tmp_path, ["a"], REVISION)
    b = build_source_manifest(tmp_path, ["b"], REVISION)
    assert a["source_bundle_sha256"] != b["source_bundle_sha256"]
    assert a["files"][0]["sha256"] == hashlib.sha256(b"same").hexdigest()


def test_web_release_config_rejects_duplicate_json_key(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"shaiwei-web-component-release-config-v2",'
        '"schema_version":"duplicate"}',
        encoding="utf-8",
    )
    with pytest.raises(BuildIdentityError, match="duplicate key"):
        load_web_release_config(path, root=ROOT)


def test_gitignore_keeps_release_build_manifest_untracked() -> None:
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".web-release/" in lines
    assert json.loads((ROOT / "config/web_component_release_v2.json").read_text())["state_path"].startswith(
        ".release/"
    )
