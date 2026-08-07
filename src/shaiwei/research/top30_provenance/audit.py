"""Independent no-Qlib audit of the M6-3C-R3 numeric provenance report."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct
from typing import Any

import pandas as pd

from shaiwei.research.top30_diagnostic.exact import COLUMNS, DiagnosticError, exact_rows
from shaiwei.research.top30_provenance.contract import (
    Protocol,
    ReleaseScope,
    load_mapping,
    sha256_file,
    tree_identity,
    write_once_document,
)


def _ordered(value: float) -> int:
    raw = struct.unpack(">Q", struct.pack(">d", value))[0]
    return (~raw & ((1 << 64) - 1)) if raw & (1 << 63) else raw | (1 << 63)


def _independent_topology(
    expected: list[dict[str, str]], actual: list[dict[str, str]]
) -> dict[str, Any]:
    if len(expected) != len(actual):
        raise DiagnosticError("Top30 provenance independent row count differs")
    fields: Counter[str] = Counter()
    distances: list[int] = []
    absolute: list[float] = []
    signs: Counter[str] = Counter()
    first = last = None
    for position, (left, right) in enumerate(zip(expected, actual, strict=True)):
        if left["date"] != right["date"]:
            raise DiagnosticError("Top30 provenance independent date differs")
        for field in COLUMNS:
            if left[field] == right[field]:
                continue
            a, b = float.fromhex(left[field]), float.fromhex(right[field])
            if not math.isfinite(a) or not math.isfinite(b):
                raise DiagnosticError("Top30 provenance independent value is nonfinite")
            delta = b - a
            item = {
                "position": position,
                "date": left["date"],
                "field": field,
                "expected": left[field],
                "actual": right[field],
                "ulp_distance": abs(_ordered(a) - _ordered(b)),
                "absolute_difference": abs(delta),
            }
            first = first or item
            last = item
            fields[field] += 1
            distances.append(item["ulp_distance"])
            absolute.append(abs(delta))
            signs["positive" if delta > 0 else "negative"] += 1
    ordered = sorted(distances)
    return {
        "exact_equal": not distances,
        "row_count": len(expected),
        "mismatch_cell_count": len(distances),
        "mismatch_by_field": dict(sorted(fields.items())),
        "first_mismatch": first,
        "last_mismatch": last,
        "ulp": {
            "minimum": ordered[0] if ordered else 0,
            "median": ordered[len(ordered) // 2] if ordered else 0,
            "maximum": ordered[-1] if ordered else 0,
            "one_ulp_count": sum(value == 1 for value in ordered),
        },
        "maximum_absolute_difference_diagnostic_only": max(absolute, default=0.0),
        "difference_direction": dict(sorted(signs.items())),
    }


def _rows(bundle: dict[str, Any], adapter: str) -> list[dict[str, str]]:
    first = bundle["adapters"][adapter]["replay_1"]["rows"]
    second = bundle["adapters"][adapter]["replay_2"]["rows"]
    if first != second:
        raise DiagnosticError("Top30 provenance independent internal replay differs")
    return first


def audit(
    *,
    protocol_path: Path,
    release_path: Path,
    canonical_path: Path,
    r2_root: Path,
    original_probe_path: Path,
    failed_probe_path: Path,
    collector_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    protocol = Protocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(audit_root.iterdir()):
        raise DiagnosticError("Top30 provenance audit output already exists")
    report = load_mapping(collector_root / "report.json")
    canonical_frame = pd.read_parquet(canonical_path)
    canonical = exact_rows(canonical_frame.set_index("datetime").sort_index())
    original = load_mapping(r2_root / "original/bundle.json")
    current = load_mapping(r2_root / "current/bundle.json")
    lanes = {
        "original_image_original_adapter": _rows(original, "original_execution"),
        "failed_image_original_adapter": _rows(current, "original_execution"),
        "failed_image_new_adapter": _rows(current, "new_execution"),
    }
    topology = {name: _independent_topology(canonical, rows) for name, rows in lanes.items()}
    observed_inputs = {
        "canonical_report": {"sha256": sha256_file(canonical_path), "size": canonical_path.stat().st_size},
        "r2_diagnostic_tree": tree_identity(r2_root),
    }
    facts = report.get("classification_facts", {})
    if facts.get("unique_cause_proven") is True and facts.get("competing_explanation_count") == 0:
        classification = "ROOT_CAUSE_IDENTIFIED"
    elif facts.get("canonical_producer_identity_complete") is True and facts.get("input_identity_pass") is True:
        classification = "PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN"
    elif facts.get("canonical_producer_identity_complete") is False:
        classification = "PROVENANCE_GAP_CONFIRMED"
    else:
        classification = "MIXED_UNRESOLVED"
    checks = {
        "scope_identity": report.get("provenance_scope_sha256") == release.sha256,
        "frozen_input_identity": observed_inputs == release.scope["inputs"],
        "collector_input_identity": report.get("input_identity", {}).get("observed") == observed_inputs,
        "topology_independent_recompute": report.get("existing_row_topology") == topology,
        "classification_independent_recompute": report.get("classification") == classification,
        "causal_claim_not_overstated": report.get("causal_proof") is False,
        "zero_new_backtest": all(
            load_mapping(path).get("top30_backtest_count") == 0
            and load_mapping(path).get("top20_backtest_count") == 0
            for path in (original_probe_path, failed_probe_path)
        ),
        "non_production": report.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        raise DiagnosticError("Top30 provenance independent audit failed")
    document = {
        "schema_version": "m6-top30-numeric-provenance-independent-audit-v1",
        "provenance_scope_sha256": release.sha256,
        "report_sha256": sha256_file(collector_root / "report.json"),
        "checks": checks,
        "independent_topology": topology,
        "classification": classification,
        "independent_audit": "PASS",
        "top20_remains_prohibited": True,
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }
    digest, reused = write_once_document(audit_root / "audit.json", document)
    return {"audit_sha256": digest, "reused": reused, "classification": classification}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol_path",
        "release_path",
        "canonical_path",
        "r2_root",
        "original_probe_path",
        "failed_probe_path",
        "collector_root",
        "audit_root",
    ):
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
