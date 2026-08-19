"""Independent recomputation audit for the RF-0B preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.research.rf_0b.contract import (
    RFBError,
    RFBRecovery,
    RFBR3AuditorRecovery,
    RFBScope,
    active_output_paths,
    validate_bound_inputs,
)
from shaiwei.research.rf_0b.fields import evaluate_field_gate, real_field_profile
from shaiwei.research.rf_0b.profile import _write_json_once
from shaiwei.research.rf_0b.registry import build_identity_registry


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RFBError(f"RF-0B audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise RFBError(f"RF-0B audit input is not an object: {path.name}")
    return value


def audit_once() -> dict[str, Any]:
    scope = RFBScope.load()
    recovery = RFBRecovery.load_if_present()
    r3 = RFBR3AuditorRecovery.load_if_present()
    if r3 is not None and recovery is None:
        raise RFBError("RF-0B R3 auditor recovery requires the R2 recovery chain")
    paths = active_output_paths(recovery)
    if recovery is not None:
        recovery.validate_parent_evidence()
    if r3 is not None:
        r3.validate_parent_evidence()
    audit_path = paths.root / "audit_r3.json" if r3 is not None else paths.audit
    if audit_path.exists():
        raise RFBError("RF-0B audit exists; same-scope audit rerun is forbidden")
    validate_bound_inputs(scope)
    profile = _read_json(paths.profile)
    manifest = _read_json(paths.manifest)
    registry = build_identity_registry(scope)
    fields = native(real_field_profile(scope, paths.root / "duckdb-tmp-audit"))
    gate = evaluate_field_gate(fields, scope.document["field_quality_gate"])
    expected_verdict = "GO_FORMAL_PROTOCOL" if gate["pass"] else "BLOCKED_DATA"
    artifact_hashes = {
        "identity_registry": sha256_file(paths.registry),
        "field_profile": sha256_file(paths.field_profile),
        "profile": sha256_file(paths.profile),
    }
    checks = {
        "protocol_identity": profile.get("protocol_sha256") == scope.sha256,
        "registry_recomputed": _read_json(paths.registry) == json.loads(canonical_json(registry)),
        "field_profile_recomputed": _read_json(paths.field_profile) == json.loads(
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
        "schema_version": "rf-0b-field-identity-preflight-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "recovery_scope_sha256": None if recovery is None else recovery.sha256,
        "auditor_r3_scope_sha256": None if r3 is None else r3.sha256,
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
    _write_json_once(audit_path, audit)
    if verdict != "PASS":
        raise RFBError("RF-0B independent audit failed")
    return audit
