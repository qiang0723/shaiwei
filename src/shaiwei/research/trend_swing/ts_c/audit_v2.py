"""Independent recomputation audit for the TS-C v2 qualification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_sha256, native
from shaiwei.research.trend_swing.ts_c.contract import (
    TQCError,
    TQC2Scope,
    V2_OUTPUT_ROOT,
    validate_v2_bound_inputs,
)
from shaiwei.research.trend_swing.ts_c.profile_v2 import (
    _write_json_once,
    evaluate_density_v2,
    real_events_v2,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TQCError(f"TS-C v2 audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise TQCError(f"TS-C v2 audit input is not an object: {path.name}")
    return value


def audit_v2_once() -> dict[str, Any]:
    root = V2_OUTPUT_ROOT
    audit_path = root / "audit.json"
    if audit_path.exists():
        raise TQCError("TS-C v2 audit exists; same-scope audit rerun is forbidden")
    scope = TQC2Scope.load()
    validate_v2_bound_inputs(scope)
    profile = _read_json(root / "profile.json")
    manifest = _read_json(root / "manifest.json")
    rows = pq.read_table(root / "events.parquet").to_pylist()
    recomputed_events, permission = real_events_v2(scope, root / "duckdb-tmp-audit")
    density = evaluate_density_v2(
        recomputed_events, permission["permission_on_years"], scope.document["density_gate"]
    )
    artifact_hashes = {
        "events": sha256_file(root / "events.parquet"),
        "profile": sha256_file(root / "profile.json"),
    }
    checks = {
        "protocol_identity": profile.get("protocol_sha256") == scope.sha256,
        "events_recomputed": [tuple(sorted(row.items())) for row in recomputed_events]
        == [tuple(sorted(row.items())) for row in rows],
        "permission_rule_recomputed": profile.get("permission_on_year_rule") == native(permission),
        "density_recomputed": profile.get("density") == native(density),
        "manifest_hashes": all(
            manifest["artifacts"][name]["sha256"] == digest
            for name, digest in artifact_hashes.items()
        ),
        "profile_payload_hash": profile.get("canonical_payload_sha256") == canonical_sha256(
            {key: value for key, value in profile.items() if key != "canonical_payload_sha256"}
        ),
        "verdict": profile.get("verdict") == density["verdict"],
        "authority": profile.get("strategy_effective") == "NOT_EVALUATED"
        and profile.get("production_authorization") == "none"
        and all(value is False or value == 0 for value in profile.get("authority", {}).values()),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "ts-c-trigger-qualification-v2-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "profile_sha256": artifact_hashes["profile"],
        "checks": native(checks),
        "independent_recomputed_payload_sha256": canonical_sha256(density),
        "outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    _write_json_once(audit_path, audit)
    if verdict != "PASS":
        raise TQCError("TS-C v2 independent audit failed")
    return audit
