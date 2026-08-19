"""Independent recomputation audit for the RF-0C preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.research.rf_0b.fields import evaluate_field_gate
from shaiwei.research.rf_0c.contract import (
    AUDIT_PATH,
    FIELD_PROFILE_PATH,
    MANIFEST_PATH,
    PROFILE_PATH,
    REGISTRY_PATH,
    RFCError,
    RFCScope,
    validate_bound_inputs,
)
from shaiwei.research.rf_0c.fields import real_field_profile
from shaiwei.research.rf_0c.profile import _write_json_once
from shaiwei.research.rf_0c.registry import build_registry_with_reproduction_check


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RFCError(f"RF-0C audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise RFCError(f"RF-0C audit input is not an object: {path.name}")
    return value


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise RFCError("RF-0C audit exists; same-scope audit rerun is forbidden")
    scope = RFCScope.load()
    validate_bound_inputs(scope)
    profile = _read_json(PROFILE_PATH)
    manifest = _read_json(MANIFEST_PATH)
    registry = build_registry_with_reproduction_check(scope)
    fields = native(real_field_profile(scope, AUDIT_PATH.parent / "duckdb-tmp-audit"))
    gate = evaluate_field_gate(fields, scope.document["field_quality_gate"])
    expected_verdict = "GO_FORMAL_PROTOCOL" if gate["pass"] else "BLOCKED_DATA"
    artifact_hashes = {
        "identity_registry": sha256_file(REGISTRY_PATH),
        "field_profile": sha256_file(FIELD_PROFILE_PATH),
        "profile": sha256_file(PROFILE_PATH),
    }
    checks = {
        "protocol_identity": profile.get("protocol_sha256") == scope.sha256,
        "registry_recomputed_and_reproduces_rf_0b": _read_json(REGISTRY_PATH) == json.loads(
            canonical_json(registry)
        ),
        "field_profile_recomputed": _read_json(FIELD_PROFILE_PATH) == json.loads(
            canonical_json(fields)
        ),
        "field_gate": profile.get("field_gate") == native(gate),
        "manifest_hashes": all(
            manifest["artifacts"][name]["sha256"] == digest
            for name, digest in artifact_hashes.items()
        ),
        "profile_payload_hash": profile.get("canonical_payload_sha256") == canonical_sha256(
            {key: value for key, value in profile.items() if key != "canonical_payload_sha256"}
        ),
        "verdict": profile.get("verdict") == expected_verdict,
        "authority": profile.get("strategy_effective") == "NOT_EVALUATED"
        and profile.get("production_authorization") == "none"
        and all(value is False or value == 0 for value in profile.get("authority", {}).values()),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "rf-0c-field-identity-preflight-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "profile_sha256": artifact_hashes["profile"],
        "checks": native(checks),
        "independent_recomputed_payload_sha256": canonical_sha256({
            "gate": gate, "verdict": expected_verdict,
            "registry_hashes": registry["total_unique_expression_hashes"],
        }),
        "outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    _write_json_once(AUDIT_PATH, audit)
    if verdict != "PASS":
        raise RFCError("RF-0C independent audit failed")
    return audit
