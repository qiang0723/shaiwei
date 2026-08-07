"""Independent, no-Qlib audit and classification of M6 Top30 diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.top30_diagnostic.contract import (
    Approval,
    Protocol,
    ReleaseScope,
    mapping,
    runtime_identity,
    write_once_document,
)
from shaiwei.research.top30_diagnostic.exact import DiagnosticError


AUDIT_COLUMNS = ("gross_return", "benchmark_return", "recorded_cost", "turnover")


def _json_sha(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_rows(path: Path) -> list[dict[str, str]]:
    frame = pd.read_parquet(path)
    expected = ["datetime", *AUDIT_COLUMNS]
    if list(frame.columns) != expected:
        raise DiagnosticError("Top30 independent audit report schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame = frame.set_index("datetime").sort_index()
    if frame.empty or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise DiagnosticError("Top30 independent audit report index differs")
    rows: list[dict[str, str]] = []
    for day, row in frame.iterrows():
        encoded = {"date": pd.Timestamp(day).strftime("%Y-%m-%d")}
        for column in AUDIT_COLUMNS:
            number = float(row[column])
            if not math.isfinite(number):
                raise DiagnosticError("Top30 independent audit report contains nonfinite data")
            encoded[column] = number.hex()
        rows.append(encoded)
    return rows


def _diff(expected: list[dict[str, str]], actual: list[dict[str, str]]) -> dict[str, Any]:
    count = 0
    first: dict[str, str] | None = None
    maximum = 0.0
    for position in range(max(len(expected), len(actual))):
        if position >= len(expected) or position >= len(actual):
            count += 1
            if first is None:
                first = {
                    "position": str(position),
                    "field": "ROW_PRESENCE",
                    "expected": "PRESENT" if position < len(expected) else "ABSENT",
                    "actual": "PRESENT" if position < len(actual) else "ABSENT",
                }
            continue
        for field in ("date", *AUDIT_COLUMNS):
            left, right = expected[position][field], actual[position][field]
            if left == right:
                continue
            count += 1
            if field != "date":
                maximum = max(maximum, abs(float.fromhex(left) - float.fromhex(right)))
            if first is None:
                first = {
                    "position": str(position),
                    "field": field,
                    "expected": left,
                    "actual": right,
                }
    return {
        "exact_equal": count == 0,
        "expected_row_count": len(expected),
        "actual_row_count": len(actual),
        "mismatch_cell_count": count,
        "first_mismatch": first,
        "maximum_absolute_difference_diagnostic_only": maximum,
    }


def _rows(bundle: dict[str, Any], adapter: str, replay: str) -> list[dict[str, str]]:
    try:
        value = bundle["adapters"][adapter][replay]["rows"]
    except (KeyError, TypeError) as error:
        raise DiagnosticError("Top30 independent audit lane bundle is incomplete") from error
    if not isinstance(value, list) or not value:
        raise DiagnosticError("Top30 independent audit replay rows are absent")
    return value


def classify_exact(
    canonical: list[dict[str, str]],
    original: dict[str, Any],
    current: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    a1 = _rows(original, "original_execution", "replay_1")
    a2 = _rows(original, "original_execution", "replay_2")
    b1 = _rows(current, "original_execution", "replay_1")
    b2 = _rows(current, "original_execution", "replay_2")
    c1 = _rows(current, "new_execution", "replay_1")
    c2 = _rows(current, "new_execution", "replay_2")
    lanes = {"original_image_original_adapter": (a1, a2),
             "failed_image_original_adapter": (b1, b2),
             "failed_image_new_adapter": (c1, c2)}
    internal = {name: left == right for name, (left, right) in lanes.items()}
    equality = {
        "original_vs_canonical": a1 == canonical,
        "failed_original_vs_canonical": b1 == canonical,
        "failed_new_vs_canonical": c1 == canonical,
        "original_vs_failed_original": a1 == b1,
        "failed_original_vs_failed_new": b1 == c1,
        "original_vs_failed_new": a1 == c1,
    }
    if not all(internal.values()):
        classification = "RUNTIME_NONDETERMINISM"
    elif all(equality[key] for key in (
        "original_vs_canonical", "failed_original_vs_canonical", "failed_new_vs_canonical"
    )):
        classification = "NO_CURRENT_MISMATCH_REPRODUCED"
    elif (
        equality["original_vs_canonical"]
        and equality["failed_original_vs_canonical"]
        and not equality["failed_new_vs_canonical"]
    ):
        classification = "NEW_ADAPTER_DIVERGENCE"
    elif (
        equality["original_vs_canonical"]
        and not equality["failed_original_vs_canonical"]
        and not equality["failed_new_vs_canonical"]
        and equality["failed_original_vs_failed_new"]
    ):
        classification = "FAILED_IMAGE_ENVIRONMENT_DIVERGENCE"
    elif (
        not equality["original_vs_canonical"]
        and not equality["failed_original_vs_canonical"]
        and not equality["failed_new_vs_canonical"]
        and equality["original_vs_failed_original"]
        and equality["failed_original_vs_failed_new"]
    ):
        classification = "HISTORICAL_REPRODUCIBILITY_GAP"
    else:
        classification = "MIXED_UNRESOLVED"
    diagnostics = {
        "internal_replay_exact_equal": internal,
        "cross_lane_exact_equal": equality,
        "versus_canonical": {
            name: {replay: _diff(canonical, rows) for replay, rows in zip(
                ("replay_1", "replay_2"), pair, strict=True
            )}
            for name, pair in lanes.items()
        },
    }
    return classification, diagnostics


def _load_bundle(root: Path, expected_lane: str) -> tuple[dict[str, Any], dict[str, str]]:
    expected_files = {"authorization.json", "diagnostic_started.json", "bundle.json"}
    actual = {path.name for path in root.iterdir() if path.is_file()}
    if actual != expected_files:
        raise DiagnosticError("Top30 independent audit lane file set differs")
    bundle = mapping(root / "bundle.json")
    if bundle.get("lane") != expected_lane or bundle.get("top20_backtest_count") != 0:
        raise DiagnosticError("Top30 independent audit lane identity differs")
    return bundle, {name: sha256_file(root / name) for name in sorted(expected_files)}


def audit(
    *,
    protocol_path: Path,
    release_path: Path,
    approval_path: Path,
    canonical_report: Path,
    original_root: Path,
    current_root: Path,
    audit_root: Path,
    runtime_verifier: Any = runtime_identity,
) -> dict[str, Any]:
    protocol = Protocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = runtime_verifier(release, "current")
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(audit_root.iterdir()):
        raise DiagnosticError("Top30 independent audit output exists")
    canonical = _canonical_rows(canonical_report)
    case = protocol.document["frozen_diagnostic_case"]["canonical_report"]
    if sha256_file(canonical_report) != case["sha256"]:
        raise DiagnosticError("Top30 independent audit canonical report identity differs")
    original, original_files = _load_bundle(original_root, "original")
    current, current_files = _load_bundle(current_root, "current")
    checks = {
        "scope_identity": original.get("diagnostic_scope_sha256") == release.sha256
        and current.get("diagnostic_scope_sha256") == release.sha256,
        "approval_identity": original.get("approval_sha256") == approval.sha256
        and current.get("approval_sha256") == approval.sha256,
        "canonical_identity": original.get("canonical_rows_sha256") == _json_sha(canonical)
        and current.get("canonical_rows_sha256") == _json_sha(canonical)
        and original.get("canonical_rows") == canonical
        and current.get("canonical_rows") == canonical,
        "execution_counts": original.get("top30_backtest_count") == 2
        and current.get("top30_backtest_count") == 4,
        "zero_top20": original.get("top20_backtest_count") == 0
        and current.get("top20_backtest_count") == 0,
        "zero_attempt_increment": original.get("research_attempt_increment") == 0
        and current.get("research_attempt_increment") == 0,
        "non_production": original.get("production_authorization") == "none"
        and current.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        failed = [name for name, value in checks.items() if not value]
        raise DiagnosticError(f"Top30 independent audit checks failed: {failed}")
    classification, diagnostics = classify_exact(canonical, original, current)
    document = {
        "schema_version": "m6-top30-compatibility-diagnostic-independent-audit-v1",
        "diagnostic_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "runtime_identity": runtime,
        "canonical_report_sha256": case["sha256"],
        "canonical_rows_sha256": _json_sha(canonical),
        "original_lane_files": original_files,
        "current_lane_files": current_files,
        "checks": checks,
        "diagnostics": diagnostics,
        "classification": classification,
        "independent_audit": "PASS",
        "top20_remains_prohibited": True,
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }
    digest, reused = write_once_document(audit_root / "audit.json", document)
    return {
        "audit_sha256": digest,
        "reused": reused,
        "classification": classification,
        "independent_audit": "PASS",
        "top20_remains_prohibited": True,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", dest="protocol_path", type=Path, required=True)
    parser.add_argument("--release", dest="release_path", type=Path, required=True)
    parser.add_argument("--approval", dest="approval_path", type=Path, required=True)
    parser.add_argument("--canonical-report", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
