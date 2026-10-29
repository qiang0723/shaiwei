"""Independent recomputation audit for the TP-F-0B profile; evidence is mounted read-only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.tp_f_0b.contract import AUDIT_ROOT, CONTROL_ROOT, OUTPUT_ROOT, TPFError, TPFScope
from shaiwei.research.tp_f_0b.profile import AUTHORITY, compute, write_json_once
from shaiwei.research.tp_f_0b.scope import data_facts, load_approved, verify
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TPFError(f"TP-F-0B audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise TPFError(f"TP-F-0B audit input is not an object: {path.name}")
    return value


def audit_once(
    scope_sha: str,
    *,
    control: Path = CONTROL_ROOT,
    root: Path = PROJECT_ROOT,
    evidence_root: Path = OUTPUT_ROOT,
    audit_root: Path = AUDIT_ROOT,
    facts: Callable[[TPFScope], dict[str, Any]] = data_facts,
    code: str | None = None,
    limits: dict[str, float] | None = None,
    alpha158: Callable[[], list[str]] | None = None,
) -> dict[str, Any]:
    from shaiwei.config import load
    from shaiwei.provenance import code_snapshot_sha256
    from shaiwei.research.tp_f_0b.registry import alpha158_expressions

    envelope = load_approved(scope_sha, control)
    contract = TPFScope.load(root)
    audit_path = audit_root / envelope.scope.execution_id / "audit.json"
    if audit_path.exists():
        raise TPFError("TP-F-0B audit exists; same-scope audit rerun is forbidden")
    verify(envelope, contract, code=code or code_snapshot_sha256(), facts=facts(contract))
    directory = evidence_root / envelope.scope.execution_id
    profile, manifest = _read(directory / "profile.json"), _read(directory / "manifest.json")
    registry, fields = _read(directory / "identity_registry.json"), _read(directory / "field_profile.json")
    expected_profile, expected_registry, expected_fields = compute(
        contract, root=root, limits=limits or load().limit_rules.model_dump(), alpha158=alpha158 or alpha158_expressions
    )
    names = {"semantic_read_marker": "semantic_read_started.json", "identity_registry": "identity_registry.json",
             "field_profile": "field_profile.json", "profile": "profile.json"}
    recomputed = json.loads(canonical_json(expected_profile))
    checks = {
        "scope_identity": profile.get("scope_sha256") == scope_sha and manifest.get("scope_sha256") == scope_sha
        and profile.get("execution_id") == envelope.scope.execution_id,
        "registry_recomputed": registry == json.loads(canonical_json(expected_registry)),
        "field_profile_recomputed": fields == json.loads(canonical_json(expected_fields)),
        "profile_recomputed": all(profile.get(key) == value for key, value in recomputed.items()),
        "manifest_hashes": all(manifest["artifacts"].get(name) == sha256_file(directory / filename) for name, filename in names.items()),
        "profile_payload_hash": profile.get("canonical_payload_sha256")
        == canonical_sha256({key: value for key, value in profile.items() if key != "canonical_payload_sha256"}),
        "deterministic_replay": profile.get("internal_deterministic_replay_pass") is True,
        "authority": profile.get("authority") == AUTHORITY and profile.get("strategy_effective") == "NOT_EVALUATED"
        and profile.get("production_authorization") == "none",
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "tp-f-0b-independent-audit-v1",
        "scope_sha256": scope_sha,
        "execution_id": envelope.scope.execution_id,
        "profile_sha256": sha256_file(directory / "profile.json"),
        "checks": checks,
        "recomputed_verdict": expected_profile["verdict"],
        "outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    write_json_once(audit_path, audit)
    if verdict != "PASS":
        raise TPFError(f"TP-F-0B independent audit failed: {[name for name, ok in checks.items() if not ok]}")
    return audit
