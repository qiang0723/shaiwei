"""Independent recomputation audit for the RF-0C preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.research.rf_0b.fields import evaluate_field_gate
from shaiwei.research.rf_0c.contract import (
    RFCError,
    RFCRecovery,
    RFCScope,
    active_root,
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
    scope = RFCScope.load()
    recovery = RFCRecovery.load_if_present()
    root = active_root(recovery)
    if recovery is not None:
        recovery.validate_parent_evidence()
    audit_path = root / "audit.json"
    if audit_path.exists():
        raise RFCError("RF-0C audit exists; same-scope audit rerun is forbidden")
    validate_bound_inputs(scope)
    profile = _read_json(root / "profile.json")
    manifest = _read_json(root / "manifest.json")
    registry = build_registry_with_reproduction_check(scope)
    fields = native(real_field_profile(scope, root / "duckdb-tmp-audit"))
    gate = evaluate_field_gate(fields, scope.document["field_quality_gate"])
    expected_verdict = "GO_FORMAL_PROTOCOL" if gate["pass"] else "BLOCKED_DATA"
    artifact_hashes = {
        "identity_registry": sha256_file(root / "identity_registry.json"),
        "field_profile": sha256_file(root / "field_profile.json"),
        "profile": sha256_file(root / "profile.json"),
    }
    checks = {
        "protocol_identity": profile.get("protocol_sha256") == scope.sha256,
        "registry_recomputed_and_reproduces_rf_0b": _read_json(
            root / "identity_registry.json"
        ) == json.loads(canonical_json(registry)),
        "field_profile_recomputed": _read_json(root / "field_profile.json") == json.loads(
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
        "recovery_scope_sha256": None if recovery is None else recovery.sha256,
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
        raise RFCError("RF-0C independent audit failed")
    return audit
