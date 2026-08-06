"""Materialize an exact hard-linked input bundle only after release approval is verified."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .contract import InputManifest, M5DataProtocol, M5GateError, canonical_json, sha256_file
from .release import ApprovalEnvelope, DataReleaseScope
from .source_reader import _bound_path, _verify_file


CONTROL_DESTINATIONS = {
    "input_manifest": "config/m5_dynamic_fundamental_data_input_v1.json",
    "release_scope": "config/m5_dynamic_fundamental_data_gate_release_scope_v1.json",
    "approval_envelope": "config/m5_dynamic_fundamental_data_gate_approval_v1.json",
}


def _build_destination(protocol: M5DataProtocol) -> str:
    suffix = "v2" if protocol.recovery_mode else "v1"
    return f"config/m5_dynamic_fundamental_data_gate_build_{suffix}.yaml"


def _project_file(project_root: Path, source: Path) -> Path:
    if source.is_symlink():
        raise M5GateError("M5 input bundle forbids symlinked control files")
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(project_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M5GateError("M5 input bundle control file is outside project root") from exc
    if not resolved.is_file():
        raise M5GateError("M5 input bundle control artifact is not a file")
    return resolved


def _link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != sha256_file(source):
            raise M5GateError("M5 input bundle destination collision differs")
        return
    os.link(source, destination)


def _expected_data_files(
    manifest: InputManifest,
    *,
    project_root: Path,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in manifest.document["sources"]:
        for batch in source["batches"]:
            relative = str(batch["relative_path"])
            path = _bound_path(project_root, relative)
            _verify_file(path, batch)
            prior = result.setdefault(relative, batch)
            if prior["content_sha256"] != batch["content_sha256"]:
                raise M5GateError("M5 input manifest aliases one path to different content")
    for item in manifest.document["memberships"]:
        relative = str(item["relative_path"])
        path = _bound_path(project_root, relative)
        _verify_file(path, item)
        prior = result.setdefault(relative, item)
        if prior["content_sha256"] != item["content_sha256"]:
            raise M5GateError("M5 membership path aliases different content")
    return result


def _bundle_inventory(
    root: Path,
    *,
    input_manifest: InputManifest,
    release: DataReleaseScope,
    approval: ApprovalEnvelope,
    input_manifest_path: Path,
    build_contract_path: Path,
    release_scope_path: Path,
    approval_envelope_path: Path,
) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "bundle_manifest.json":
            continue
        files.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": "m5-input-bundle-v2",
        "input_manifest_sha256": input_manifest.sha256,
        "input_manifest_physical_sha256": sha256_file(input_manifest_path),
        "build_contract_sha256": sha256_file(build_contract_path),
        "release_scope_sha256": release.sha256,
        "release_scope_physical_sha256": sha256_file(release_scope_path),
        "approval_envelope_sha256": approval.sha256,
        "approval_envelope_physical_sha256": sha256_file(approval_envelope_path),
        "file_count": len(files),
        "files": files,
        "semantic_rows_read": False,
    }


def materialize_bundle(
    protocol: M5DataProtocol,
    manifest: InputManifest,
    release: DataReleaseScope,
    approval: ApprovalEnvelope,
    *,
    project_root: Path,
    bundle_root: Path,
    input_manifest_path: Path,
    build_contract_path: Path,
    release_scope_path: Path,
    approval_envelope_path: Path,
) -> dict[str, Any]:
    target = bundle_root
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise M5GateError("existing M5 input bundle is not a regular directory")
        manifest_path = target / "bundle_manifest.json"
        if not manifest_path.is_file():
            raise M5GateError("existing M5 input bundle is partial")
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = _bundle_inventory(
            target,
            input_manifest=manifest,
            release=release,
            approval=approval,
            input_manifest_path=input_manifest_path,
            build_contract_path=build_contract_path,
            release_scope_path=release_scope_path,
            approval_envelope_path=approval_envelope_path,
        )
        if stored != expected or manifest_path.read_text(encoding="utf-8") != canonical_json(stored) + "\n":
            raise M5GateError("existing M5 input bundle identity differs")
        return stored
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
    if temporary.exists():
        raise M5GateError("M5 input bundle temporary directory already exists")
    temporary.mkdir(mode=0o700)
    try:
        data_files = _expected_data_files(manifest, project_root=project_root)
        for relative, item in data_files.items():
            source = _bound_path(project_root, relative)
            _verify_file(source, item)
            _link(source, temporary / relative)
        frozen = protocol.build_document["frozen_inputs"]
        for item in frozen.values():
            relative = str(item["path"])
            source = _project_file(project_root, project_root / relative)
            if sha256_file(source) != item["sha256"]:
                raise M5GateError("M5 frozen control input changed before bundling")
            _link(source, temporary / relative)
        controls = {
            CONTROL_DESTINATIONS["input_manifest"]: input_manifest_path,
            _build_destination(protocol): build_contract_path,
            CONTROL_DESTINATIONS["release_scope"]: release_scope_path,
            CONTROL_DESTINATIONS["approval_envelope"]: approval_envelope_path,
        }
        for relative, source_path in controls.items():
            _link(_project_file(project_root, source_path), temporary / relative)
        inventory = _bundle_inventory(
            temporary,
            input_manifest=manifest,
            release=release,
            approval=approval,
            input_manifest_path=input_manifest_path,
            build_contract_path=build_contract_path,
            release_scope_path=release_scope_path,
            approval_envelope_path=approval_envelope_path,
        )
        (temporary / "bundle_manifest.json").write_text(
            canonical_json(inventory) + "\n", encoding="utf-8"
        )
        os.replace(temporary, target)
        return inventory
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M5DataProtocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=args.project_root,
        )
        manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        input_mount = next(
            item for item in release.scope["container"]["mounts"] if item["target"] == "/inputs"
        )
        result = materialize_bundle(
            protocol,
            manifest,
            release,
            approval,
            project_root=args.project_root,
            bundle_root=args.project_root / input_mount["source"],
            input_manifest_path=args.input_manifest,
            build_contract_path=args.build_contract,
            release_scope_path=args.release_scope,
            approval_envelope_path=args.approval_envelope,
        )
    except (M5GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
