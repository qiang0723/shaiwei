"""TP-F-1 stage A: independent read-only audit of generation, blind review, family accounting, selection and judgement."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from shaiwei.config import Settings, load
from shaiwei.ledger import EXPERIMENTS, resolve_artifact_path, sha256_file
from shaiwei.research.g1_calibration.ledger_view import complete_rows
from shaiwei.research.g1_v2_rejudge.judge import RejudgeRoots, judge_unit
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2
from shaiwei.research.tp_f_1.contract import FAMILY, TPF1Error
from shaiwei.research.tp_f_1.evaluate import judge_view, select_top_two
from shaiwei.research.tp_f_1.generate import write_json_once
from shaiwei.research.tp_f_1.review import parse_ruling
from shaiwei.research.tp_f_1.scope import (
    ATTEMPTS, AUDIT_ROOT, CONTROL_ROOT, OUTPUT_ROOT, REPORTS_ROOT, load_approved, review_path, scope_attempts,
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_once(
    scope_sha: str,
    *,
    control: Path = CONTROL_ROOT,
    output_root: Path = OUTPUT_ROOT,
    reports_root: Path = REPORTS_ROOT,
    audit_root: Path = AUDIT_ROOT,
    attempts_path: Path = ATTEMPTS,
    experiments: Path = EXPERIMENTS,
    admissions: Path = FACTOR_ADMISSIONS_V2,
    settings: Settings | None = None,
) -> dict[str, Any]:
    from shaiwei.research.g1_v2 import load_spec

    envelope = load_approved(scope_sha, control)
    execution = envelope.scope.execution_id
    audit_path = audit_root / execution / "audit.json"
    if audit_path.exists():
        raise TPF1Error("TP-F-1 audit exists; same-scope audit rerun is forbidden")
    root, reports = output_root / execution, reports_root / execution
    generation = _json(root / "generation/generation_summary.json")
    rows = scope_attempts(scope_sha, attempts_path)
    ruling = _json(review_path(scope_sha, control))
    packet = _json(root / "generation/blind_review_packet.json")
    summary = _json(reports / "evaluation_summary.json")
    family_rows = [row for row in complete_rows(experiments) if json.loads(row["params_json"]).get("g1_research_family") == FAMILY
                   and json.loads(row["params_json"]).get("attempt_id") in {r["attempt_id"] for r in rows}]
    evaluated = []
    for row in family_rows:
        result = json.loads(row["result_json"])
        if result.get("status") == "EVALUATED":
            cid = json.loads(row["params_json"])["candidate_id"]
            canonical = next(r["canonical_sha256"] for r in rows if r["candidate_id"] == cid)
            evaluated.append({"status": "EVALUATED", "candidate_id": cid, "discovery_abs_rank_ic": abs(float(result["discovery_mean_daily_rank_ic"])),
                              "canonical_sha256": canonical})
    settings = settings or load()
    spec = load_spec(settings)
    view = judge_view(settings, spec.spec, spec.sha256, envelope.scope.protocol_id)
    roots = RejudgeRoots(data=root / "evaluation", reports=reports, experiments=experiments, admissions=admissions)
    rejudged = []
    for item in summary["judged"]:
        decision = judge_unit(view, roots, FAMILY, item["experiment_id"], root / "evaluation" / item["experiment_id"] / "g1_evidence.json",
                              write=False)
        rejudged.append(decision["status"] == item["status"] and decision["failed_gates"] == item["failed_gates"]
                        and decision["statistics"]["increment_trial_count"] == len(rows))
    admitted_ids = {row["decision_id"] for row in complete_rows(admissions)}
    spent = sum((Decimal(row["estimated_cost_usd"]) for row in rows), Decimal(0))
    expected_verdict = ("GO_SEPARATE_ADMISSION_OR_PAPER_PROTOCOL_PROPOSAL_ONLY"
                        if any(item["status"] == "PASS" for item in summary["judged"]) else "REJECT_TP_F_AND_CLOSE")
    checks = {
        "attempts_match_generation": [row["attempt_id"] for row in rows] == generation["attempt_ids"]
        and generation["completed_responses"] == len(rows) <= 8,
        "decision_artifacts_hash": all(sha256_file(resolve_artifact_path(row["decision_artifact_path"])) == row["decision_artifact_sha256"]
                                       for row in rows),
        "cost_within_ceiling": spent == Decimal(generation["spent_usd"]) and spent <= Decimal(envelope.scope.single_batch_ceiling_usd),
        "qualified_match": generation["qualified_candidates"] == [row["candidate_id"] for row in rows if row["status"] == "QUALIFIED"],
        "blind_review_verbatim": parse_ruling(packet, ruling["verbatim_user_text"]) == ruling["decisions"]
        and ruling["scope_sha256"] == scope_sha,
        "family_n_one_row_per_response": len(family_rows) == len(rows)
        and sorted(json.loads(r["params_json"])["attempt_id"] for r in family_rows) == sorted(r["attempt_id"] for r in rows),
        "selection_recomputed": [item["candidate_id"] for item in select_top_two(evaluated)] == summary["selected"],
        "judgement_recomputed": all(rejudged) and len(rejudged) == len(summary["selected"]),
        "admissions_recorded": all(item["decision_id"] in admitted_ids for item in summary["judged"]),
        "verdict": summary["verdict"] == expected_verdict,
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {"schema_version": "tp-f-1-independent-audit-v1", "scope_sha256": scope_sha, "execution_id": execution, "checks": checks,
             "completed_responses": len(rows), "spent_usd": f"{spent:.12f}", "recomputed_verdict": expected_verdict,
             "evaluation_summary_sha256": sha256_file(reports / "evaluation_summary.json"),
             "outcome_beyond_g1_v2_read": False, "production_authorization": "none", "independent_audit": verdict}
    write_json_once(audit_path, audit)
    if verdict != "PASS":
        raise TPF1Error(f"TP-F-1 independent audit failed: {[name for name, ok in checks.items() if not ok]}")
    return audit

