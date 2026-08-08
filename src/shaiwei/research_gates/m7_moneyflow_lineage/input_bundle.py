"""Materialize exact hard-linked lineage inputs only after approval verification."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file

from .contract import LineageError, LineageInputManifest, LineageProtocol
from .release import LineageApproval, LineageRelease


CONTROL_FILES = (
    "config/m7_moneyflow_gap_lineage_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_protocol_scope_v1.json",
    "config/m7_star_custom_pool_moneyflow_proposal_export_v1.json",
    "config/m3_star_custom_pit_v1.yaml",
    "config/m3_star_custom_pit_manifest_v1.json",
    "config/m7_moneyflow_recovery_engineering_v1.yaml",
    "docs/M7_MONEYFLOW_GAP_LINEAGE_PROTOCOL_20260809.md",
    "docs/M7_MONEYFLOW_RECOVERY_ENGINEERING_ACCEPTANCE_20260808.md",
    "docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_COMPATIBILITY_PROTOCOL_20260808.md",
    "docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_PROTOCOL_FREEZE_ACCEPTANCE_20260808.md",
)
GENERATED_CONTROLS = {
    "config/m7_moneyflow_gap_lineage_input_v1.json": "manifest",
    "config/m7_moneyflow_gap_lineage_release_scope_v1.json": "release",
    "config/m7_moneyflow_gap_lineage_approval_v1.json": "approval",
}


def _file(root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise LineageError("lineage bundle forbids symlinked files")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise LineageError("lineage bundle input is outside project root") from exc
    if not resolved.is_file():
        raise LineageError("lineage bundle input is not a regular file")
    return resolved


def _link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != sha256_file(source):
            raise LineageError("lineage bundle destination collision differs")
        return
    os.link(source, destination)


def _verify_source(root: Path, item: dict[str, Any]) -> Path:
    path = _file(root, root / item["relative_path"])
    metadata = pq.read_metadata(path)
    if (
        path.stat().st_size != int(item["bytes"])
        or metadata.num_rows != int(item["row_count"])
        or list(metadata.schema.names) != item["schema_fields"]
        or sha256_file(path) != item["content_sha256"]
    ):
        raise LineageError("lineage source changed before bundling")
    return path


def _bundle_inventory(
    root: Path,
    manifest: LineageInputManifest,
    release: LineageRelease,
    approval: LineageApproval,
) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative != "bundle_manifest.json":
            files.append(
                {"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            )
    return {
        "schema_version": "m7-moneyflow-gap-lineage-input-bundle-v1",
        "input_manifest_sha256": manifest.sha256,
        "input_manifest_physical_sha256": manifest.physical_sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "file_count": len(files),
        "files": files,
        "semantic_rows_read": False,
        "numeric_moneyflow_value_columns_read": 0,
    }


def _verify_predecessor(
    project_root: Path,
    predecessor: Path,
    manifest: LineageInputManifest,
) -> list[Path]:
    manifest_path = _file(project_root, predecessor / "bundle_manifest.json")
    expected = manifest.document["predecessor_bundle"]
    if sha256_file(manifest_path) != expected["bundle_manifest_sha256"]:
        raise LineageError("lineage predecessor manifest changed")
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = document.get("files")
    if not isinstance(files, list) or len(files) != expected["file_count"]:
        raise LineageError("lineage predecessor file inventory differs")
    verified = []
    for item in files:
        path = _file(project_root, predecessor / item["relative_path"])
        if path.stat().st_size != int(item["bytes"]) or sha256_file(path) != item["sha256"]:
            raise LineageError("lineage predecessor content changed")
        verified.append(path)
    return verified


def materialize_bundle(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    release: LineageRelease,
    approval: LineageApproval,
    *,
    project_root: Path,
    bundle_root: Path,
    manifest_path: Path,
    release_path: Path,
    approval_path: Path,
) -> dict[str, Any]:
    if bundle_root.exists():
        stored = json.loads((bundle_root / "bundle_manifest.json").read_text(encoding="utf-8"))
        if stored != _bundle_inventory(bundle_root, manifest, release, approval):
            raise LineageError("existing lineage bundle identity differs")
        return stored
    temporary = bundle_root.parent / f".{bundle_root.name}.{os.getpid()}.tmp"
    if temporary.exists():
        raise LineageError("lineage temporary bundle already exists")
    temporary.mkdir(parents=True, mode=0o700)
    try:
        predecessor = project_root / manifest.document["predecessor_bundle"]["relative_path"]
        if predecessor.is_symlink() or not predecessor.is_dir():
            raise LineageError("lineage predecessor bundle differs")
        predecessor_files = _verify_predecessor(project_root, predecessor, manifest)
        predecessor_files.append(_file(project_root, predecessor / "bundle_manifest.json"))
        for source in sorted(predecessor_files):
            _link(source, temporary / "predecessor" / source.relative_to(predecessor))
        for source_document in manifest.document["sources"].values():
            for item in source_document["batches"]:
                _link(_verify_source(project_root, item), temporary / item["bundle_relative_path"])
        for relative in CONTROL_FILES:
            _link(_file(project_root, project_root / relative), temporary / relative)
        generated = {"manifest": manifest_path, "release": release_path, "approval": approval_path}
        for relative, key in GENERATED_CONTROLS.items():
            _link(_file(project_root, generated[key]), temporary / relative)
        inventory = _bundle_inventory(temporary, manifest, release, approval)
        (temporary / "bundle_manifest.json").write_text(canonical_json(inventory) + "\n", encoding="utf-8")
        bundle_root.parent.mkdir(parents=True, exist_ok=True)
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
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(args.protocol, project_root=args.project_root)
        manifest = LineageInputManifest.load(args.input_manifest, protocol)
        release = LineageRelease.load(args.release_scope, protocol, manifest)
        approval = LineageApproval.load(args.approval_envelope, release)
        result = materialize_bundle(
            protocol,
            manifest,
            release,
            approval,
            project_root=args.project_root,
            bundle_root=args.bundle_root,
            manifest_path=args.input_manifest,
            release_path=args.release_scope,
            approval_path=args.approval_envelope,
        )
    except (LineageError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
