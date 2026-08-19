"""One-shot RF-0B result-blind profile orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Mapping

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native
from shaiwei.research.rf_0b.contract import (
    RFBError,
    RFBRecovery,
    RFBScope,
    active_output_paths,
    runtime_identity,
    validate_bound_inputs,
)
from shaiwei.research.rf_0b.fields import evaluate_field_gate, real_field_profile
from shaiwei.research.rf_0b.registry import build_identity_registry


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise RFBError(f"RF-0B write-once output already exists: {path.name}")
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def build_profile(
    scope: RFBScope, identity: Mapping[str, str], temporary: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    registry = build_identity_registry(scope)
    fields = native(real_field_profile(scope, temporary))
    gate = evaluate_field_gate(fields, scope.document["field_quality_gate"])
    verdict = "GO_FORMAL_PROTOCOL" if gate["pass"] else "BLOCKED_DATA"
    profile = {
        "schema_version": "rf-0b-field-identity-preflight-profile-v1",
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
    scope = RFBScope.load()
    recovery = RFBRecovery.load_if_present()
    paths = active_output_paths(recovery)
    if recovery is not None:
        recovery.validate_parent_evidence()
    if any(
        path.exists()
        for path in (paths.marker, paths.registry, paths.field_profile, paths.profile,
                     paths.manifest, paths.audit)
    ):
        raise RFBError("RF-0B output exists; same-scope rerun is forbidden")
    validate_bound_inputs(scope)
    identity = runtime_identity()
    paths.root.mkdir(parents=True, exist_ok=True)
    marker = {
        "schema_version": "rf-0b-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": scope.sha256,
        "recovery_scope_sha256": None if recovery is None else recovery.sha256,
        "release_identity": identity,
    }
    marker_sha = _write_json_once(paths.marker, marker)
    first, registry, fields = build_profile(scope, identity, paths.root / "duckdb-tmp")
    second, registry_replay, fields_replay = build_profile(
        scope, identity, paths.root / "duckdb-tmp-replay"
    )
    if (
        canonical_json(first) != canonical_json(second)
        or canonical_json(registry) != canonical_json(registry_replay)
        or canonical_json(fields) != canonical_json(fields_replay)
    ):
        raise RFBError("RF-0B internal deterministic replay differs")
    artifacts = {
        "semantic_read_marker": {"path": _relative(paths.marker), "sha256": marker_sha},
        "identity_registry": {
            "path": _relative(paths.registry), "sha256": _write_json_once(paths.registry, registry)
        },
        "field_profile": {
            "path": _relative(paths.field_profile),
            "sha256": _write_json_once(paths.field_profile, fields),
        },
    }
    first["machine_artifacts"] = artifacts
    first["internal_deterministic_replay_pass"] = True
    first["canonical_payload_sha256"] = canonical_sha256(first)
    profile_sha = _write_json_once(paths.profile, first)
    manifest = {
        "schema_version": "rf-0b-field-identity-preflight-manifest-v1",
        "protocol_sha256": scope.sha256,
        "recovery_scope_sha256": None if recovery is None else recovery.sha256,
        "release_identity": identity,
        "artifacts": {**artifacts, "profile": {"path": _relative(paths.profile), "sha256": profile_sha}},
        "contains_outcome": False,
        "contains_security_identifiers": False,
        "production_authorization": "none",
    }
    _write_json_once(paths.manifest, manifest)
    return first
