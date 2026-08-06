"""Independent M6-2 effect auditor; never imports the primary decision modules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_sha256,
    sha256_file,
)
from shaiwei.research.model_attribution.effect_audit_reader import read_pass
from shaiwei.research.model_attribution.effect_audit_statistics import (
    independently_evaluate,
    independently_score_diagnostics,
)
from shaiwei.research.model_attribution.effect_contract import (
    EffectApproval,
    EffectProtocol,
    EffectReleaseScope,
    write_once_document,
)


def _document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AttributionError(f"M6 audit input is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise AttributionError(f"M6 audit input is not a mapping: {path.name}")
    return value


def _check_pass(
    evidence: dict[str, Any],
    protocol: EffectProtocol,
) -> tuple[dict[str, Any], dict[str, Any]]:
    effect = independently_evaluate(
        evidence["predictions"],
        evidence["labels"],
        evidence["reports"],
        evidence["stress_reports"],
        protocol.result,
    )
    diagnostics = independently_score_diagnostics(
        evidence["test_predictions"],
        evidence["top30"],
        int(protocol.result["portfolio"]["rebalance_trade_days"]),
    )
    summary = evidence["summary"]
    expected_identity = {
        "schema_version": "m6-model-attribution-pass-summary-v1",
        "protocol_sha256": protocol.sha256,
        "result_protocol_sha256": protocol.result_sha256,
        "model_fit_count": 12,
        "blend_model_fit_count": 0,
        "window_count": 6,
        "arm_count": 3,
        "strategy_effective": "NOT_YET_AUDITED",
        "production_authorization": "none",
    }
    if any(summary.get(key) != value for key, value in expected_identity.items()):
        raise AttributionError("M6 audit pass identity differs")
    if canonical_sha256(summary.get("effect")) != canonical_sha256(effect):
        raise AttributionError("M6 audit independently recomputed effect differs")
    if canonical_sha256(summary.get("score_diagnostics")) != canonical_sha256(diagnostics):
        raise AttributionError("M6 audit independently recomputed diagnostics differ")
    return effect, diagnostics


def audit(
    *,
    release_path: Path,
    approval_path: Path,
    effect_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release = EffectReleaseScope.load(release_path, protocol)
    approval = EffectApproval.load(approval_path, release)
    runtime = release.verify_runtime_identity()
    if (effect_root / "failure.json").exists():
        raise AttributionError("M6 effect failure exists; audit cannot convert it into a result")
    authorization = _document(effect_root / "authorization.json")
    marker = _document(effect_root / "effect_read_started.json")
    report = _document(effect_root / "report.json")
    if authorization != {
        "schema_version": "m6-model-attribution-run-authorization-v1",
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "action": approval.document["action"],
        "production_authorization": "none",
    }:
        raise AttributionError("M6 audit authorization identity differs")
    if marker != {
        "release_scope_sha256": release.sha256,
        "alternative_attempts_consumed": 2,
        "same_release_retry_authorized": False,
    }:
        raise AttributionError("M6 audit effect-read marker differs")
    expected_report = {
        "schema_version": "m6-model-attribution-effect-report-v1",
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "runtime_identity": runtime,
        "inputs": release.scope["inputs"],
        "deterministic_replay": True,
        "alternative_attempts_consumed": 2,
        "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
        "production_authorization": "none",
    }
    if any(report.get(key) != value for key, value in expected_report.items()):
        raise AttributionError("M6 audit effect report identity differs")
    first = read_pass(effect_root / "first_pass")
    replay = read_pass(effect_root / "replay")
    first_effect, first_diagnostics = _check_pass(first, protocol)
    replay_effect, replay_diagnostics = _check_pass(replay, protocol)
    if first["manifest"] != replay["manifest"]:
        raise AttributionError("M6 audit first pass and replay manifests differ")
    if canonical_sha256(first_effect) != canonical_sha256(replay_effect):
        raise AttributionError("M6 audit first pass and replay effects differ")
    if canonical_sha256(first_diagnostics) != canonical_sha256(replay_diagnostics):
        raise AttributionError("M6 audit first pass and replay diagnostics differ")
    for name, evidence in (("first_pass", first), ("replay", replay)):
        reported = report.get(name, {})
        if reported.get("bundle_sha256") != evidence["manifest"]["bundle_sha256"]:
            raise AttributionError(f"M6 audit {name} bundle identity differs")
        if reported.get("manifest_sha256") != sha256_file(effect_root / name / "manifest.json"):
            raise AttributionError(f"M6 audit {name} manifest identity differs")
        if reported.get("summary_sha256") != canonical_sha256(evidence["summary"]):
            raise AttributionError(f"M6 audit {name} summary identity differs")
        if reported.get("decision") != evidence["summary"]["effect"]["inference"]["decision"]:
            raise AttributionError(f"M6 audit {name} decision differs")
    decision = first_effect["inference"]["decision"]
    if report.get("decision") != decision:
        raise AttributionError("M6 audit report decision differs")
    if audit_root.exists() and any(audit_root.iterdir()):
        raise AttributionError("M6 audit output exists before the one-shot audit")
    audit_root.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": "m6-model-attribution-effect-audit-v1",
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "report_sha256": sha256_file(effect_root / "report.json"),
        "runtime_identity": runtime,
        "first_pass_bundle_sha256": first["manifest"]["bundle_sha256"],
        "replay_bundle_sha256": replay["manifest"]["bundle_sha256"],
        "independent_recalculation_sha256": canonical_sha256(first_effect),
        "checks": {
            "release_and_approval_identity": True,
            "manifest_and_artifact_hashes": True,
            "member_day_keys_and_rank_ic": True,
            "cost_active_return_turnover_drawdown": True,
            "newey_west_10_and_holm_two": True,
            "scheduled_top30_and_score_diagnostics": True,
            "first_pass_replay_exact_identity": True,
            "terminal_decision": True,
        },
        "decision": decision,
        "independent_audit": "PASS",
        "strategy_effective": "M6_ATTRIBUTION_DECISION_ONLY",
        "production_authorization": "none",
    }
    audit_sha, reused = write_once_document(audit_root / "audit.json", document)
    return {
        "audit_sha256": audit_sha,
        "reused": reused,
        "decision": decision,
        "independent_audit": "PASS",
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            audit(
                release_path=args.release,
                approval_path=args.approval,
                effect_root=args.effect_root,
                audit_root=args.audit_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
