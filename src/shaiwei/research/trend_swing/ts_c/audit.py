"""Independent recomputation audit for the TS-C trigger qualification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_sha256, native
from shaiwei.research.trend_swing.ts_c.contract import (
    AUDIT_PATH,
    EVENTS_PATH,
    MANIFEST_PATH,
    PROFILE_PATH,
    TQCError,
    TQCScope,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.ts_c.profile import _write_json_once, evaluate_density


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TQCError(f"TS-C audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise TQCError(f"TS-C audit input is not an object: {path.name}")
    return value


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise TQCError("TS-C audit exists; same-scope audit rerun is forbidden")
    scope = TQCScope.load()
    validate_bound_inputs(scope)
    profile = _read_json(PROFILE_PATH)
    manifest = _read_json(MANIFEST_PATH)
    rows = pq.read_table(EVENTS_PATH).to_pylist()
    density = evaluate_density(rows, scope.document["density_gate"])
    artifact_hashes = {
        "events": sha256_file(EVENTS_PATH),
        "profile": sha256_file(PROFILE_PATH),
    }
    checks = {
        "protocol_identity": profile.get("protocol_sha256") == scope.sha256,
        "density_recomputed": profile.get("density") == native(density),
        "event_keys_unique": len({(row["trigger_id"], row["ts_code"], row["signal_date"]) for row in rows}) == len(rows),
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
        "schema_version": "ts-c-trigger-qualification-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "profile_sha256": artifact_hashes["profile"],
        "checks": native(checks),
        "independent_recomputed_payload_sha256": canonical_sha256(density),
        "outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    _write_json_once(AUDIT_PATH, audit)
    if verdict != "PASS":
        raise TQCError("TS-C independent audit failed")
    return audit
