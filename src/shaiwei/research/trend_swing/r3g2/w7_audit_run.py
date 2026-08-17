"""Separate no-Qlib auditor entrypoint for the completed W7 lineage run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json
from shaiwei.research.trend_swing.r3g2.w7_audit import audit_pair
from shaiwei.research.trend_swing.r3g2.w7_control import Approval, ReleaseScope


RuntimeVerifier = Callable[[ReleaseScope], dict[str, str]]


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error(f"R3G-2 W7 audit input is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G2Error(f"R3G-2 W7 audit input is not a mapping: {path.name}")
    return value


def run_audit(
    *,
    release_path: Path,
    approval_path: Path,
    lineage_root: Path,
    audit_root: Path,
    runtime_verifier: RuntimeVerifier = lambda release: release.verify_runtime_identity(),
) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = runtime_verifier(release)
    if audit_root.exists() and any(audit_root.iterdir()):
        raise R3G2Error("R3G-2 W7 audit output exists")
    expected_entries = {
        "authorization.json",
        "lineage_read_started.json",
        "first_pass",
        "replay",
        "report.json",
    }
    if {path.name for path in lineage_root.iterdir()} != expected_entries:
        raise R3G2Error("R3G-2 W7 completed lineage file set differs")
    authorization = _json(lineage_root / "authorization.json")
    started = _json(lineage_root / "lineage_read_started.json")
    report = _json(lineage_root / "report.json")
    if (
        authorization.get("release_scope_sha256") != release.sha256
        or authorization.get("approval_sha256") != approval.sha256
        or authorization.get("action") != approval.document["action"]
        or authorization.get("strategy_effect_attempt_count") != 0
        or started.get("release_scope_sha256") != release.sha256
        or started.get("complete_passes") != ["first_pass", "replay"]
        or started.get("same_release_retry_authorized") is not False
        or started.get("strategy_effect_attempt_count") != 0
        or report.get("release_scope_sha256") != release.sha256
        or report.get("approval_sha256") != approval.sha256
        or report.get("inputs") != release.scope["inputs"]
        or report.get("runtime_identity") != runtime
        or report.get("deterministic_replay") is not True
        or report.get("label_rankic_return_or_effect_read") is not False
        or report.get("verdict") != "PENDING_INDEPENDENT_W7_LINEAGE_AUDIT"
        or report.get("strategy_effect_attempt_count") != 0
    ):
        raise R3G2Error("R3G-2 W7 report binding differs")
    evidence = audit_pair(lineage_root / "first_pass", lineage_root / "replay", protocol)
    audit = {
        **evidence,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "runtime_identity": runtime,
        "strategy_effect_attempt_count": 0,
        "verdict": "GO_W7_SCORE_LINEAGE_DATA_ONLY",
    }
    digest, reused = write_once_json(audit_root / "audit.json", audit)
    return {"audit_sha256": digest, "reused": reused, "verdict": audit["verdict"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--lineage-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run_audit(
                release_path=args.release,
                approval_path=args.approval,
                lineage_root=args.lineage_root,
                audit_root=args.audit_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
