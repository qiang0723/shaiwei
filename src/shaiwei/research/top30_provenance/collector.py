"""One-shot collector over sealed M6 Top30 artifacts and secret-free image probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import yaml

from shaiwei.research.top30_diagnostic.exact import COLUMNS, DiagnosticError, exact_rows
from shaiwei.research.top30_provenance.classification import classify
from shaiwei.research.top30_provenance.contract import (
    Protocol,
    ReleaseScope,
    load_mapping,
    sha256_file,
    tree_identity,
    write_once_document,
)
from shaiwei.research.top30_provenance.topology import compare_rows, lane_rows


THREAD_NAMES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def _canonical_rows(path: Path) -> list[dict[str, str]]:
    frame = pd.read_parquet(path)
    expected = ["datetime", *COLUMNS]
    if list(frame.columns) != expected:
        raise DiagnosticError("Top30 provenance canonical schema differs")
    return exact_rows(frame.set_index("datetime").sort_index())


def _parquet_metadata(path: Path) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    metadata = parquet.metadata
    compressions = sorted(
        {
            metadata.row_group(group).column(column).compression
            for group in range(metadata.num_row_groups)
            for column in range(metadata.row_group(group).num_columns)
        }
    )
    return {
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "created_by": metadata.created_by,
        "format_version": metadata.format_version,
        "num_rows": metadata.num_rows,
        "num_row_groups": metadata.num_row_groups,
        "schema": str(parquet.schema_arrow),
        "compressions": compressions,
        "mtime_ns_diagnostic_only": path.stat().st_mtime_ns,
    }


def _service_runtime(path: Path, service: str) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    row = document["services"][service]
    environment = row.get("environment", {})
    return {
        "image": row.get("image"),
        "command": row.get("command"),
        "cpus": float(row.get("cpus")),
        "memory": row.get("mem_limit"),
        "pids_limit": row.get("pids_limit"),
        "thread_environment": {name: str(environment.get(name, "ABSENT")) for name in THREAD_NAMES},
        "network_mode": row.get("network_mode"),
        "read_only_root": row.get("read_only"),
    }


def _probe(path: Path, role: str, release: ReleaseScope) -> dict[str, Any]:
    value = load_mapping(path)
    expected_runtime = release.scope["images"][role]
    runtime = value.get("runtime_identity", {})
    if (
        value.get("schema_version") != "m6-top30-numeric-provenance-image-probe-v1"
        or value.get("provenance_scope_sha256") != release.sha256
        or runtime.get("role") != role
        or any(runtime.get(key) != expected_runtime[key] for key in ("git_commit", "base_image_id"))
        or value.get("top30_backtest_count") != 0
        or value.get("top20_backtest_count") != 0
    ):
        raise DiagnosticError(f"Top30 provenance {role} image probe differs")
    return value


def _input_identity(
    release: ReleaseScope, canonical_path: Path, r2_root: Path
) -> dict[str, Any]:
    expected = release.scope["inputs"]
    observed = {
        "canonical_report": {"sha256": sha256_file(canonical_path), "size": canonical_path.stat().st_size},
        "r2_diagnostic_tree": tree_identity(r2_root),
    }
    return {"expected": expected, "observed": observed, "pass": observed == expected}


def collect(
    *,
    protocol_path: Path,
    release_path: Path,
    canonical_path: Path,
    r2_root: Path,
    original_probe_path: Path,
    failed_probe_path: Path,
    original_release_path: Path,
    failed_release_path: Path,
    canonical_compose_path: Path,
    diagnostic_compose_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    protocol = Protocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    output_root.mkdir(parents=True, exist_ok=True)
    if any(output_root.iterdir()):
        raise DiagnosticError("Top30 provenance collector output already exists")
    write_once_document(
        output_root / "collector_started.json",
        {
            "schema_version": "m6-top30-numeric-provenance-collector-start-v1",
            "provenance_scope_sha256": release.sha256,
            "top30_backtest_count": 0,
            "top20_backtest_count": 0,
            "same_scope_retry_authorized": False,
        },
    )
    identity = _input_identity(release, canonical_path, r2_root)
    if not identity["pass"]:
        raise DiagnosticError("Top30 provenance frozen input identity differs")
    original_probe = _probe(original_probe_path, "original", release)
    failed_probe = _probe(failed_probe_path, "failed", release)
    original_release = load_mapping(original_release_path)["scope"]
    failed_release = load_mapping(failed_release_path)["scope"]
    original_bundle = load_mapping(r2_root / "original/bundle.json")
    current_bundle = load_mapping(r2_root / "current/bundle.json")
    r2_audit = load_mapping(r2_root / "audit/audit.json")
    canonical = _canonical_rows(canonical_path)
    if original_bundle.get("canonical_rows") != canonical or current_bundle.get("canonical_rows") != canonical:
        raise DiagnosticError("Top30 provenance canonical rows differ from sealed R2 evidence")
    lanes = {
        "original_image_original_adapter": lane_rows(original_bundle, "original_execution"),
        "failed_image_original_adapter": lane_rows(current_bundle, "original_execution"),
        "failed_image_new_adapter": lane_rows(current_bundle, "new_execution"),
    }
    topology = {name: compare_rows(canonical, rows) for name, rows in lanes.items()}
    canonical_runtime = _service_runtime(canonical_compose_path, "m6-effect-runner")
    diagnostic_runtime = _service_runtime(
        diagnostic_compose_path, "m6-top30-diagnostic-recovery-original"
    )
    canonical_image = original_release["image"]
    producer_fields = (
        "image_id",
        "git_commit",
        "code_snapshot_sha256",
        "release_manifest_sha256",
        "platform",
    )
    canonical_producer_complete = all(canonical_image.get(field) for field in producer_fields)
    canonical_producer_complete = bool(
        canonical_producer_complete
        and original_probe["runtime_identity"]["base_image_id"] == canonical_image["image_id"]
        and original_release["inputs"]["qlib_tree_sha256"]
        == failed_release["inputs"]["qlib"]["qlib_tree_sha256"]
    )
    package_differences = {
        name: {"original": original_probe["distributions"].get(name), "failed": value}
        for name, value in failed_probe["distributions"].items()
        if original_probe["distributions"].get(name) != value
    }
    source_differences = {
        name: {"original": original_probe["source_identity"].get(name), "failed": value}
        for name, value in failed_probe["source_identity"].items()
        if original_probe["source_identity"].get(name) != value
    }
    runtime_differences = {
        key: {"canonical": canonical_runtime[key], "diagnostic": diagnostic_runtime[key]}
        for key in ("command", "cpus", "memory", "pids_limit", "thread_environment")
        if canonical_runtime[key] != diagnostic_runtime[key]
    }
    facts = {
        "input_identity_pass": True,
        "canonical_producer_identity_complete": canonical_producer_complete,
        "unique_cause_proven": False,
        "competing_explanation_count": len(runtime_differences) + len(package_differences) + len(source_differences),
    }
    classification = classify(facts)
    report = {
        "schema_version": "m6-top30-numeric-provenance-report-v1",
        "provenance_scope_sha256": release.sha256,
        "input_identity": identity,
        "canonical_artifact": _parquet_metadata(canonical_path),
        "canonical_producer": canonical_image,
        "canonical_runtime": canonical_runtime,
        "diagnostic_runtime": diagnostic_runtime,
        "image_probes": {"original": original_probe, "failed": failed_probe},
        "package_differences": package_differences,
        "source_differences": source_differences,
        "runtime_differences": runtime_differences,
        "existing_row_topology": topology,
        "r2_exact_relationship": r2_audit["diagnostics"]["cross_lane_exact_equal"],
        "classification_facts": facts,
        "classification": classification,
        "causal_proof": False,
        "top20_remains_prohibited": True,
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }
    digest, reused = write_once_document(output_root / "report.json", report)
    return {"report_sha256": digest, "reused": reused, "classification": classification}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol_path",
        "release_path",
        "canonical_path",
        "r2_root",
        "original_probe_path",
        "failed_probe_path",
        "original_release_path",
        "failed_release_path",
        "canonical_compose_path",
        "diagnostic_compose_path",
        "output_root",
    ):
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
