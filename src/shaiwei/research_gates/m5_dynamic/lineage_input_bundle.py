"""Materialize exact M5 lineage inputs only after release approval is verified."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from .contract import M5GateError, canonical_json, sha256_file
from .lineage_contract import CONTROL_PATHS, LineageInputManifest, LineageProtocol
from .lineage_release import LineageApprovalEnvelope, LineageReleaseScope


def _project_file(project_root: Path, source: Path) -> Path:
    if source.is_symlink():
        raise M5GateError("M5 lineage bundle forbids symlinked inputs")
    try:
        path = source.resolve(strict=True)
        path.relative_to(project_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M5GateError("M5 lineage bundle input is outside project") from exc
    if not path.is_file():
        raise M5GateError("M5 lineage bundle input is not a file")
    return path


def _verify_batch(path: Path, item: dict[str, Any]) -> None:
    metadata = pq.read_metadata(path)
    if (
        sha256_file(path) != item["content_sha256"]
        or path.stat().st_size != int(item["bytes"])
        or int(metadata.num_rows) != int(item["row_count"])
        or list(metadata.schema.names) != list(item["schema_fields"])
    ):
        raise M5GateError("M5 lineage bundle batch differs from manifest")


def _link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != sha256_file(source):
            raise M5GateError("M5 lineage bundle destination collision differs")
        return
    os.link(source, destination)


def _inventory(
    root: Path,
    *,
    manifest: LineageInputManifest,
    release: LineageReleaseScope,
    approval: LineageApprovalEnvelope,
) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative != "bundle_manifest.json":
            files.append(
                {
                    "relative_path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return {
        "schema_version": "m5-source-lineage-input-bundle-v1",
        "input_manifest_sha256": manifest.sha256,
        "release_scope_sha256": release.sha256,
        "approval_envelope_sha256": approval.sha256,
        "file_count": len(files),
        "files": files,
        "semantic_rows_read": False,
    }


def materialize_lineage_bundle(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    release: LineageReleaseScope,
    approval: LineageApprovalEnvelope,
    *,
    project_root: Path,
    bundle_root: Path,
    build_path: Path,
    manifest_path: Path,
    release_path: Path,
    approval_path: Path,
) -> dict[str, Any]:
    expected_root = project_root / next(
        item["source"] for item in release.scope["container"]["mounts"] if item["target"] == "/lineage-input"
    )
    if bundle_root.resolve() != expected_root.resolve():
        raise M5GateError("M5 lineage bundle root differs from release")
    if bundle_root.exists():
        stored_path = bundle_root / "bundle_manifest.json"
        if bundle_root.is_symlink() or not stored_path.is_file():
            raise M5GateError("existing M5 lineage bundle is partial")
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        expected = _inventory(
            bundle_root,
            manifest=manifest,
            release=release,
            approval=approval,
        )
        if stored != expected or stored_path.read_text(encoding="utf-8") != canonical_json(stored) + "\n":
            raise M5GateError("existing M5 lineage bundle identity differs")
        return stored
    bundle_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = bundle_root.parent / f".{bundle_root.name}.{os.getpid()}.tmp"
    if temporary.exists():
        raise M5GateError("M5 lineage bundle temporary directory exists")
    temporary.mkdir(mode=0o700)
    try:
        batches: dict[str, dict[str, Any]] = {}
        for name in ("anchor_sources", "history_sources"):
            for source in manifest.document[name]:
                for item in source["batches"]:
                    relative = item["relative_path"]
                    prior = batches.setdefault(relative, item)
                    if prior["content_sha256"] != item["content_sha256"]:
                        raise M5GateError("M5 lineage bundle path aliases different content")
        for relative, item in batches.items():
            source = _project_file(project_root, project_root / relative)
            _verify_batch(source, item)
            _link(source, temporary / relative)
        for item in protocol.build_document["frozen_inputs"].values():
            relative = item["path"]
            source = _project_file(project_root, project_root / relative)
            if sha256_file(source) != item["sha256"]:
                raise M5GateError("M5 lineage frozen control changed")
            _link(source, temporary / relative)
        controls = {
            CONTROL_PATHS["build"]: build_path,
            CONTROL_PATHS["manifest"]: manifest_path,
            CONTROL_PATHS["release"]: release_path,
            CONTROL_PATHS["approval"]: approval_path,
        }
        for relative, source in controls.items():
            _link(_project_file(project_root, source), temporary / relative)
        inventory = _inventory(
            temporary,
            manifest=manifest,
            release=release,
            approval=approval,
        )
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
    parser.add_argument("--protocol-scope", type=Path, required=True)
    parser.add_argument("--research-config", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(
            protocol_path=args.protocol,
            build_path=args.build_contract,
            scope_path=args.protocol_scope,
            project_root=args.project_root,
        )
        manifest = LineageInputManifest.load(args.input_manifest)
        research = yaml.safe_load(args.research_config.read_text(encoding="utf-8"))
        release = LineageReleaseScope.load(
            args.release_scope,
            protocol,
            manifest,
            source_proposal=research["source_proposal"],
        )
        approval = LineageApprovalEnvelope.load(args.approval_envelope, release)
        bundle = args.project_root / next(
            item["source"]
            for item in release.scope["container"]["mounts"]
            if item["target"] == "/lineage-input"
        )
        result = materialize_lineage_bundle(
            protocol,
            manifest,
            release,
            approval,
            project_root=args.project_root,
            bundle_root=bundle,
            build_path=args.build_contract,
            manifest_path=args.input_manifest,
            release_path=args.release_scope,
            approval_path=args.approval_envelope,
        )
    except (M5GateError, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
