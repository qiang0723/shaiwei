"""Build and verify a pushed, content-addressed local Web release candidate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
from typing import Mapping

from shaiwei.build_identity.multi_image_release import (
    BUILD_SNAPSHOT_LABEL,
    IMAGE_ROLE_LABEL,
    MULTI_IMAGE_ATTESTATION_SCHEMA,
    REVISION_LABEL,
    SOURCE_BUNDLE_LABEL,
    canonical_multi_image_attestation_sha256,
    verify_multi_image_attestation,
)
from shaiwei.build_identity.registry import PROJECT_ROOT, load_build_registry
from shaiwei.build_identity.release import (
    component_asset_records,
    component_build_snapshot_sha256,
)
from shaiwei.build_identity.source_bundle import (
    build_source_manifest,
    verify_source_manifest,
)
from shaiwei.build_identity.web_release_config import (
    WebReleaseConfig,
    WebReleaseError,
    load_web_release_config,
)
from shaiwei.build_identity.web_release_runtime import scheduler_identity


CANDIDATE_SCHEMA = "shaiwei-web-component-candidate-v1"
_CANDIDATE_KEYS = {
    "schema_version",
    "candidate_sha256",
    "generated_at",
    "release_key_sha256",
    "source_manifest",
    "attestation",
    "verification",
    "scheduler_identity_before",
    "build_attempts_by_role",
}
_IDENTITY_LABELS = (REVISION_LABEL, BUILD_SNAPSHOT_LABEL, SOURCE_BUNDLE_LABEL, IMAGE_ROLE_LABEL)


def _run(
    argv: list[str],
    *,
    root: Path,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise WebReleaseError(f"command failed: {' '.join(argv)}: {detail}")
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_candidate_sha256(document: Mapping[str, object]) -> str:
    unsigned = {key: value for key, value in document.items() if key != "candidate_sha256"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _write_json_atomic(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def pushed_git_identity(root: Path) -> str:
    head = _run(["git", "rev-parse", "HEAD"], root=root).stdout.strip()
    origin = _run(["git", "rev-parse", "origin/main"], root=root).stdout.strip()
    if head != origin:
        raise WebReleaseError("Web release requires HEAD synchronized with origin/main")
    return head


def _require_release_revision_ancestor(root: Path, revision: str) -> str:
    current = pushed_git_identity(root)
    ancestor = _run(
        ["git", "merge-base", "--is-ancestor", revision, current],
        root=root,
        check=False,
    )
    if ancestor.returncode not in {0, 1}:
        raise WebReleaseError("Git could not verify Web release ancestry")
    if ancestor.returncode:
        raise WebReleaseError("Web release build revision is not an ancestor of current pushed HEAD")
    return current


def _source_names(root: Path, config: WebReleaseConfig, build_assets: tuple[str, ...]) -> list[str]:
    selectors = [*config.source_roots, *config.source_files]
    tracked = _run(["git", "ls-files", "-z", "--", *selectors], root=root).stdout
    names = sorted(name for name in tracked.split("\0") if name)
    if not set(config.source_files) <= set(names):
        raise WebReleaseError("Web release source files are not all tracked")
    if any(not any(name.startswith(f"{source_root}/") for name in names) for source_root in config.source_roots):
        raise WebReleaseError("Web release source root has no tracked files")
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", *selectors],
        root=root,
    ).stdout
    if untracked:
        raise WebReleaseError("Web release source domain contains untracked files")
    release_inputs = sorted({*names, *build_assets})
    dirty = _run(["git", "diff", "--quiet", "HEAD", "--", *release_inputs], root=root, check=False)
    if dirty.returncode not in {0, 1}:
        raise WebReleaseError("Git could not verify Web release input cleanliness")
    if dirty.returncode:
        raise WebReleaseError("Web release inputs differ from pushed HEAD")
    return names


def _inspect_image(root: Path, reference: str) -> dict[str, object]:
    template = "|".join(
        [
            "{{.Id}}",
            *[f'{{{{index .Config.Labels "{label}"}}}}' for label in _IDENTITY_LABELS],
        ]
    )
    output = _run(["docker", "image", "inspect", "--format", template, reference], root=root)
    parts = output.stdout.strip().split("|")
    if len(parts) != 5:
        raise WebReleaseError(f"candidate image identity is incomplete: {reference}")
    return {
        "image_id": parts[0],
        "labels": dict(zip(_IDENTITY_LABELS, parts[1:], strict=True)),
    }


def _embedded_manifest_identity(root: Path, reference: str, container_path: str) -> str:
    code = (
        "import json; from pathlib import Path; "
        f"d=json.loads(Path({container_path!r}).read_text()); print(d.get('manifest_sha256',''))"
    )
    output = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--entrypoint",
            "python",
            reference,
            "-c",
            code,
        ],
        root=root,
    ).stdout.strip()
    if len(output) != 64:
        raise WebReleaseError(f"candidate image embedded manifest is invalid: {reference}")
    return output


def _build_image(
    root: Path,
    *,
    reference: str,
    dockerfile: str,
    role: str,
    revision: str,
    build_snapshot: str,
    source_bundle: str,
) -> None:
    if _run(["docker", "image", "inspect", reference], root=root, check=False).returncode == 0:
        raise WebReleaseError(f"candidate image reference already exists before build: {reference}")
    env = {**os.environ, "DOCKER_BUILDKIT": "1"}
    _run(
        [
            "docker",
            "build",
            "--file",
            dockerfile,
            "--tag",
            reference,
            "--build-arg",
            f"SHAIWEI_COMPONENT_GIT_COMMIT={revision}",
            "--build-arg",
            f"SHAIWEI_COMPONENT_BUILD_SNAPSHOT_SHA256={build_snapshot}",
            "--build-arg",
            f"SHAIWEI_SOURCE_BUNDLE_SHA256={source_bundle}",
            "--build-arg",
            f"SHAIWEI_COMPONENT_IMAGE_ROLE={role}",
            ".",
        ],
        root=root,
        env=env,
    )


def _release_key(registry_sha: str, build_sha: str, source_sha: str, revision: str) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "registry_sha256": registry_sha,
                "component_build_snapshot_sha256": build_sha,
                "source_bundle_sha256": source_sha,
                "git_commit": revision,
            }
        )
    ).hexdigest()


def build_candidate(*, root: Path | None = None) -> dict[str, object]:
    project_root = (root or PROJECT_ROOT).resolve()
    config = load_web_release_config(root=project_root)
    if (project_root / config.candidate_path).is_file():
        return load_and_verify_candidate(root=project_root)
    registry = load_build_registry(root=project_root)
    component = registry.component(config.component_id)
    revision = pushed_git_identity(project_root)
    names = _source_names(project_root, config, component.assets)
    manifest = build_source_manifest(project_root, names, revision)
    manifest_path = project_root / config.embedded_manifest_build_path
    _write_json_atomic(manifest_path, manifest)
    verify_source_manifest(manifest, root=project_root)
    build_assets = component_asset_records(component.assets, project_root)
    build_snapshot = component_build_snapshot_sha256(build_assets)
    source_bundle = str(manifest["source_bundle_sha256"])
    release_key = _release_key(registry.registry_sha256, build_snapshot, source_bundle, revision)

    image_rows: list[dict[str, object]] = []
    attempts: dict[str, int] = {}
    for spec in config.images:
        reference = f"{spec.repository}-{release_key[:16]}"
        _build_image(
            project_root,
            reference=reference,
            dockerfile=spec.dockerfile,
            role=spec.role,
            revision=revision,
            build_snapshot=build_snapshot,
            source_bundle=source_bundle,
        )
        attempts[spec.role] = 1
        inspected = _inspect_image(project_root, reference)
        embedded = _embedded_manifest_identity(
            project_root, reference, config.embedded_manifest_container_path
        )
        image_rows.append(
            {
                "role": spec.role,
                "dockerfile": spec.dockerfile,
                "services": list(spec.services),
                "image_reference": reference,
                "image_id": inspected["image_id"],
                "labels": inspected["labels"],
                "embedded_manifest_sha256": embedded,
            }
        )

    attestation: dict[str, object] = {
        "schema_version": MULTI_IMAGE_ATTESTATION_SCHEMA,
        "attestation_sha256": "",
        "component_id": config.component_id,
        "registry_id": registry.registry_id,
        "registry_schema_version": registry.schema_version,
        "registry_sha256": registry.registry_sha256,
        "build_assets": build_assets,
        "component_build_snapshot_sha256": build_snapshot,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_bundle_sha256": source_bundle,
        "source_file_count": manifest["source_file_count"],
        "git_commit": revision,
        "origin_main": revision,
        "images": image_rows,
        "production_authorization": "none",
    }
    attestation["attestation_sha256"] = canonical_multi_image_attestation_sha256(attestation)
    verification = verify_multi_image_attestation(
        attestation, registry, config.images, manifest, root=project_root
    )
    candidate: dict[str, object] = {
        "schema_version": CANDIDATE_SCHEMA,
        "candidate_sha256": "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_key_sha256": release_key,
        "source_manifest": manifest,
        "attestation": attestation,
        "verification": verification,
        "scheduler_identity_before": scheduler_identity(project_root),
        "build_attempts_by_role": attempts,
    }
    candidate["candidate_sha256"] = canonical_candidate_sha256(candidate)
    _write_json_atomic(project_root / config.candidate_path, candidate)
    return candidate


def load_and_verify_candidate(*, root: Path | None = None) -> dict[str, object]:
    project_root = (root or PROJECT_ROOT).resolve()
    config = load_web_release_config(root=project_root)
    path = project_root / config.candidate_path
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WebReleaseError("Web release candidate is missing or invalid") from error
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_KEYS:
        raise WebReleaseError("Web release candidate schema differs")
    if candidate.get("schema_version") != CANDIDATE_SCHEMA:
        raise WebReleaseError("Web release candidate version differs")
    if candidate.get("candidate_sha256") != canonical_candidate_sha256(candidate):
        raise WebReleaseError("Web release candidate identity differs")
    manifest, attestation = candidate.get("source_manifest"), candidate.get("attestation")
    if not isinstance(manifest, dict) or not isinstance(attestation, dict):
        raise WebReleaseError("Web release candidate documents are invalid")
    release_revision = manifest.get("git_commit")
    if not isinstance(release_revision, str) or attestation.get("git_commit") != release_revision:
        raise WebReleaseError("Web release candidate Git identities differ")
    _require_release_revision_ancestor(project_root, release_revision)
    verify_source_manifest(manifest, root=project_root)
    registry = load_build_registry(root=project_root)
    component = registry.component(config.component_id)
    current_names = _source_names(project_root, config, component.assets)
    manifest_names = [row.get("path") for row in manifest.get("files", []) if isinstance(row, dict)]
    if manifest_names != current_names:
        raise WebReleaseError("Web release candidate source inventory differs from current HEAD")
    verification = verify_multi_image_attestation(
        attestation, registry, config.images, manifest, root=project_root
    )
    if candidate.get("verification") != verification:
        raise WebReleaseError("Web release candidate verification differs")
    attempts = candidate.get("build_attempts_by_role")
    if attempts != {spec.role: 1 for spec in config.images}:
        raise WebReleaseError("Web release candidate build-attempt evidence differs")
    for row in attestation["images"]:
        inspected = _inspect_image(project_root, str(row["image_reference"]))
        if inspected != {"image_id": row["image_id"], "labels": row["labels"]}:
            raise WebReleaseError(f"candidate image daemon identity differs: {row['role']}")
        embedded = _embedded_manifest_identity(
            project_root, str(row["image_reference"]), config.embedded_manifest_container_path
        )
        if embedded != row["embedded_manifest_sha256"]:
            raise WebReleaseError(f"candidate embedded manifest differs: {row['role']}")
    return candidate
