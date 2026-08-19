"""Independent recomputation audit for the RF gap-lineage diagnostic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.config import PROJECT_ROOT
from shaiwei.research.rf_diag.contract import (
    AUDIT_PATH,
    MANIFEST_PATH,
    OUTPUT_ROOT,
    REPORT_PATH,
    RFDError,
    RFDScope,
    validate_bound_inputs,
)
from shaiwei.research.rf_diag.diagnose import run_diagnostic
from shaiwei.research.rf_diag.run import _write_json_once


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RFDError(f"RF diagnostic audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise RFDError(f"RF diagnostic audit input is not an object: {path.name}")
    return value


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise RFDError("RF diagnostic audit exists; same-scope audit rerun is forbidden")
    scope = RFDScope.load()
    validate_bound_inputs(scope)
    report = _read_json(REPORT_PATH)
    manifest_doc = _read_json(MANIFEST_PATH)
    raw_manifest = load_r3_manifest(
        PROJECT_ROOT / scope.document["frozen_inputs"]["raw_market_store"][
            "r3_frozen_input_manifest"
        ]["path"]
    )
    recomputed = native(run_diagnostic(scope, OUTPUT_ROOT / "duckdb-tmp-audit", raw_manifest))
    comparable = {key: value for key, value in report.items()
                  if key not in {"machine_artifacts", "internal_deterministic_replay_pass",
                                 "canonical_payload_sha256", "release_identity"}}
    artifact_hashes = {
        "report": sha256_file(REPORT_PATH),
    }
    checks = {
        "protocol_identity": report.get("protocol_sha256") == scope.sha256,
        "diagnostic_recomputed": json.loads(canonical_json(comparable)) == json.loads(
            canonical_json(recomputed)
        ),
        "manifest_hashes": manifest_doc["artifacts"]["report"]["sha256"] == artifact_hashes["report"],
        "profile_payload_hash": report.get("canonical_payload_sha256") == canonical_sha256(
            {key: value for key, value in report.items() if key != "canonical_payload_sha256"}
        ),
        "verdict_values": report.get("verdict") in (
            "DIAGNOSIS_COMPLETE_ALL_EXPLAINED",
            "DIAGNOSIS_COMPLETE_UNEXPLAINED_REMAINS",
        ),
        "authority": report.get("strategy_effective") == "NOT_EVALUATED"
        and report.get("production_authorization") == "none"
        and all(value is False or value == 0 for value in report.get("authority", {}).values()),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "rf-0b-gap-lineage-diagnostic-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "report_sha256": artifact_hashes["report"],
        "checks": native(checks),
        "independent_recomputed_payload_sha256": canonical_sha256(recomputed),
        "outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    _write_json_once(AUDIT_PATH, audit)
    if verdict != "PASS":
        raise RFDError("RF diagnostic independent audit failed")
    return audit
