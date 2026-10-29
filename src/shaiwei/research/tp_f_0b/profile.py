"""TP-F-0B profile computation and the one-shot write-once execution (protocol §7)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping

import duckdb

from shaiwei.research.tp_f_0b.contract import TPFError, TPFScope
from shaiwei.research.tp_f_0b.fields import classify_panel, evaluate_gates, field_profile, final_verdict
from shaiwei.research.tp_f_0b.panel import PanelParams, build_panel
from shaiwei.research.tp_f_0b.registry import alpha158_expressions, build_extension_registry, identity_verdict
from shaiwei.research.trend_swing.recovery_store import configure_store
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256, native


AUTHORITY = {
    "candidate_value_or_score_computed": False,
    "feature_distribution_output": False,
    "outcome_or_return_read": False,
    "llm_call": 0,
    "external_api_calls": 0,
    "secret_read": False,
    "ledger_write": False,
    "strategy_effect_attempt_increment": 0,
}


def _summary(registry: Mapping[str, Any]) -> dict[str, Any]:
    layers = registry["extension_layers"]
    return {
        "sealed_base": registry["sealed_base"],
        "public_factor_references": layers["public_factor_references"],
        "ts_v5_semantic_layer": {key: value for key, value in layers["ts_v5_semantic_layer"].items() if not key.endswith("hashes")},
        "g1_v2_rejudge": layers["g1_v2_rejudge"],
        "joint_state_census": registry["joint_state_census"],
    }


def compute(
    scope: TPFScope,
    *,
    root: Path,
    limits: Mapping[str, float],
    alpha158: Callable[[], list[str]] = alpha158_expressions,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Returns (profile, identity registry, field profile); every output is a count, ratio or identity hash."""
    params = PanelParams.from_protocol(scope.document)
    manifest = json.loads((root / scope.manifest_relative).read_text(encoding="utf-8"))
    connection = duckdb.connect(":memory:")
    try:
        with tempfile.TemporaryDirectory(prefix="tp-f-0b-duckdb-") as temporary:
            configure_store(connection, Path(temporary))
            panel = build_panel(connection, manifest, params, root=root, qlib_root=root / scope.qlib_root_relative, limits=limits)
    finally:
        connection.close()
    fields = native(field_profile(panel, classify_panel(panel, params), params))
    del panel
    gate = native(evaluate_gates(fields, scope.document["gates"]))
    registry = native(build_extension_registry(scope, alpha158=alpha158, root=root))
    identity = identity_verdict(registry)
    profile = {
        "schema_version": "tp-f-0b-data-identity-preflight-profile-v1",
        "protocol_sha256": scope.sha256,
        "addendum_a1_sha256": scope.addendum_sha256,
        "field_gate": gate,
        "identity_verdict": identity,
        "identity_registry_summary": _summary(registry),
        "authority": AUTHORITY,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": final_verdict(gate, identity),
    }
    return profile, registry, fields


def write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise TPFError(f"TP-F-0B write-once output already exists: {path.name}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
    return hashlib.sha256(payload).hexdigest()


def run_once(
    scope: TPFScope,
    *,
    scope_sha256: str,
    execution_id: str,
    release: Mapping[str, str],
    root: Path,
    output_root: Path,
    limits: Mapping[str, float],
    alpha158: Callable[[], list[str]] = alpha158_expressions,
) -> dict[str, Any]:
    directory = output_root / execution_id
    try:
        directory.mkdir(parents=True, exist_ok=False)  # 排他认领：目录已在即视为同 scope 重跑
    except FileExistsError as exc:
        raise TPFError("TP-F-0B execution directory exists; same-scope rerun is forbidden") from exc
    marker = {
        "schema_version": "tp-f-0b-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scope_sha256": scope_sha256,
        "release_identity": dict(release),
    }
    artifacts = {"semantic_read_marker": write_json_once(directory / "semantic_read_started.json", marker)}
    first = compute(scope, root=root, limits=limits, alpha158=alpha158)
    second = compute(scope, root=root, limits=limits, alpha158=alpha158)
    if any(canonical_json(left) != canonical_json(right) for left, right in zip(first, second, strict=True)):
        raise TPFError("TP-F-0B internal deterministic replay differs")
    profile, registry, fields = first
    artifacts["identity_registry"] = write_json_once(directory / "identity_registry.json", registry)
    artifacts["field_profile"] = write_json_once(directory / "field_profile.json", fields)
    profile = {**profile, "scope_sha256": scope_sha256, "execution_id": execution_id, "release_identity": dict(release),
               "machine_artifacts": dict(artifacts), "internal_deterministic_replay_pass": True}
    profile["canonical_payload_sha256"] = canonical_sha256(profile)
    artifacts["profile"] = write_json_once(directory / "profile.json", profile)
    write_json_once(directory / "manifest.json", {
        "schema_version": "tp-f-0b-data-identity-preflight-manifest-v1",
        "scope_sha256": scope_sha256,
        "execution_id": execution_id,
        "artifacts": artifacts,
        "contains_outcome": False,
        "contains_security_identifiers": False,
        "production_authorization": "none",
    })
    return {"execution_id": execution_id, "verdict": profile["verdict"], "field_gate_pass": profile["field_gate"]["pass"],
            "identity_verdict": profile["identity_verdict"]}
