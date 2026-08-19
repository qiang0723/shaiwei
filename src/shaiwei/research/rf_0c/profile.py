"""One-shot RF-0C result-blind profile orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Mapping

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.research.rf_0b.fields import evaluate_field_gate
from shaiwei.research.rf_0c.contract import (
    AUDIT_PATH,
    FIELD_PROFILE_PATH,
    MANIFEST_PATH,
    MARKER_PATH,
    OUTPUT_ROOT,
    PROFILE_PATH,
    REGISTRY_PATH,
    RFCError,
    RFCScope,
    runtime_identity,
    validate_bound_inputs,
)
from shaiwei.research.rf_0c.fields import real_field_profile
from shaiwei.research.rf_0c.registry import build_registry_with_reproduction_check


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise RFCError(f"RF-0C write-once output already exists: {path.name}")
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def build_profile(
    scope: RFCScope, identity: Mapping[str, str], temporary: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    registry = build_registry_with_reproduction_check(scope)
    fields = native(real_field_profile(scope, temporary))
    gate = evaluate_field_gate(fields, scope.document["field_quality_gate"])
    verdict = "GO_FORMAL_PROTOCOL" if gate["pass"] else "BLOCKED_DATA"
    profile = {
        "schema_version": "rf-0c-field-identity-preflight-profile-v1",
        "protocol_sha256": scope.sha256,
        "release_identity": dict(identity),
        "field_gate": gate,
        "identity_registry_summary": {
            key: {
                item_key: item
                for item_key, item in section.items()
                if not item_key.endswith("hashes") and item_key != "identity_tokens"
            }
            for key, section in registry["sections"].items()
        },
        "total_unique_expression_hashes": registry["total_unique_expression_hashes"],
        "registry_reproduces_sealed_rf_0b": True,
        "authority": {
            "candidate_value_or_score_computed": False,
            "outcome_or_return_read": False,
            "llm_call": 0,
            "external_api_calls": 0,
            "secret_read": False,
            "strategy_effect_attempt_increment": 0,
        },
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    return profile, registry, fields


def run_profile_once() -> dict[str, Any]:
    outputs = (MARKER_PATH, REGISTRY_PATH, FIELD_PROFILE_PATH, PROFILE_PATH, MANIFEST_PATH, AUDIT_PATH)
    if any(path.exists() for path in outputs):
        raise RFCError("RF-0C output exists; same-scope rerun is forbidden")
    scope = RFCScope.load()
    validate_bound_inputs(scope)
    identity = runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    marker = {
        "schema_version": "rf-0c-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": scope.sha256,
        "release_identity": identity,
    }
    marker_sha = _write_json_once(MARKER_PATH, marker)
    first, registry, fields = build_profile(scope, identity, OUTPUT_ROOT / "duckdb-tmp")
    second, registry_replay, fields_replay = build_profile(
        scope, identity, OUTPUT_ROOT / "duckdb-tmp-replay"
    )
    if (
        canonical_json(first) != canonical_json(second)
        or canonical_json(registry) != canonical_json(registry_replay)
        or canonical_json(fields) != canonical_json(fields_replay)
    ):
        raise RFCError("RF-0C internal deterministic replay differs")
    artifacts = {
        "semantic_read_marker": {"path": _relative(MARKER_PATH), "sha256": marker_sha},
        "identity_registry": {
            "path": _relative(REGISTRY_PATH), "sha256": _write_json_once(REGISTRY_PATH, registry)
        },
        "field_profile": {
            "path": _relative(FIELD_PROFILE_PATH),
            "sha256": _write_json_once(FIELD_PROFILE_PATH, fields),
        },
    }
    first["machine_artifacts"] = artifacts
    first["internal_deterministic_replay_pass"] = True
    first["canonical_payload_sha256"] = canonical_sha256(first)
    profile_sha = _write_json_once(PROFILE_PATH, first)
    manifest = {
        "schema_version": "rf-0c-field-identity-preflight-manifest-v1",
        "protocol_sha256": scope.sha256,
        "release_identity": identity,
        "artifacts": {**artifacts, "profile": {"path": _relative(PROFILE_PATH), "sha256": profile_sha}},
        "contains_outcome": False,
        "contains_security_identifiers": False,
        "production_authorization": "none",
    }
    _write_json_once(MANIFEST_PATH, manifest)
    return first
