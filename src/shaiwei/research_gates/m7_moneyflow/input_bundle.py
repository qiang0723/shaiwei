"""Materialize exact M7 hard-linked inputs only after approval is verified."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .contract import InputManifest, M7GateError, M7Protocol, canonical_json, sha256_file
from .release import ApprovalEnvelope, DataReleaseScope


CONTROL_DESTINATIONS = {
    "manifest": "config/m7_star_custom_pool_moneyflow_data_input_v1.json",
    "build": "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
    "release": "config/m7_star_custom_pool_moneyflow_data_gate_release_scope_v1.json",
    "approval": "config/m7_star_custom_pool_moneyflow_data_gate_approval_v1.json",
}


def _project_file(project_root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise M7GateError("M7 input bundle forbids symlinked files")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(project_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M7GateError("M7 bundle input is missing or outside project root") from exc
    if not resolved.is_file():
        raise M7GateError("M7 bundle input is not a regular file")
    return resolved


def _link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != sha256_file(source):
            raise M7GateError("M7 input bundle destination collision differs")
        return
    os.link(source, destination)


def _verify_data(project_root: Path, item: dict[str, Any], *, parquet: bool) -> Path:
    path = _project_file(project_root, project_root / item["relative_path"])
    expected_sha = item.get("content_sha256", item.get("sha256"))
    if path.stat().st_size != int(item["bytes"]) or sha256_file(path) != expected_sha:
        raise M7GateError("M7 bundle data identity differs")
    if parquet:
        metadata = pq.read_metadata(path)
        if metadata.num_rows != int(item["row_count"]) or list(metadata.schema.names) != item["schema_fields"]:
            raise M7GateError("M7 bundle Parquet footer differs")
    return path


def _inventory(root: Path, manifest: InputManifest, release: DataReleaseScope, approval: ApprovalEnvelope) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "bundle_manifest.json":
            continue
        files.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {
        "schema_version": "m7-moneyflow-input-bundle-v1",
        "input_manifest_sha256": manifest.sha256,
        "input_manifest_physical_sha256": manifest.physical_sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "file_count": len(files),
        "files": files,
        "semantic_rows_read": False,
        "numeric_moneyflow_value_columns_read": 0,
    }


def materialize_bundle(
    protocol: M7Protocol,
    manifest: InputManifest,
    release: DataReleaseScope,
    approval: ApprovalEnvelope,
    *,
    project_root: Path,
    bundle_root: Path,
    manifest_path: Path,
    build_path: Path,
    release_path: Path,
    approval_path: Path,
) -> dict[str, Any]:
    if bundle_root.exists():
        if bundle_root.is_symlink() or not bundle_root.is_dir():
            raise M7GateError("existing M7 bundle is not a regular directory")
        stored = json.loads((bundle_root / "bundle_manifest.json").read_text(encoding="utf-8"))
        if stored != _inventory(bundle_root, manifest, release, approval):
            raise M7GateError("existing M7 bundle identity differs")
        return stored
    bundle_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = bundle_root.parent / f".{bundle_root.name}.{os.getpid()}.tmp"
    if temporary.exists():
        raise M7GateError("M7 bundle temporary directory already exists")
    temporary.mkdir(mode=0o700)
    try:
        for item in manifest.document["source_batches"]:
            _link(_verify_data(project_root, item, parquet=True), temporary / item["relative_path"])
        membership = manifest.document["membership"]
        _link(_verify_data(project_root, membership, parquet=True), temporary / membership["relative_path"])
        for item in manifest.document["evidence_files"].values():
            _link(_verify_data(project_root, item, parquet=False), temporary / item["relative_path"])
        for item in protocol.build_document["frozen_inputs"].values():
            source = _project_file(project_root, project_root / item["path"])
            if sha256_file(source) != item["sha256"]:
                raise M7GateError("M7 frozen control changed before bundling")
            _link(source, temporary / item["path"])
        controls = {
            CONTROL_DESTINATIONS["manifest"]: manifest_path,
            CONTROL_DESTINATIONS["build"]: build_path,
            CONTROL_DESTINATIONS["release"]: release_path,
            CONTROL_DESTINATIONS["approval"]: approval_path,
        }
        for relative, path in controls.items():
            _link(_project_file(project_root, path), temporary / relative)
        inventory = _inventory(temporary, manifest, release, approval)
        (temporary / "bundle_manifest.json").write_text(canonical_json(inventory) + "\n", encoding="utf-8")
        os.replace(temporary, bundle_root)
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
    parser.add_argument("--bundle-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M7Protocol.load(args.protocol, build_path=args.build_contract, project_root=args.project_root)
        manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        result = materialize_bundle(
            protocol,
            manifest,
            release,
            approval,
            project_root=args.project_root,
            bundle_root=args.bundle_root,
            manifest_path=args.input_manifest,
            build_path=args.build_contract,
            release_path=args.release_scope,
            approval_path=args.approval_envelope,
        )
    except (M7GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
