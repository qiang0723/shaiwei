"""Disconnected M3-3 preexecution gate; never reads a secret or calls a provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import FAIL, PASS
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.m3_multi_pool_review_contract import (
    CANDIDATE_IDS,
    DEFAULT_PROTOCOL_PATH,
    DEFAULT_RELEASE_PATH,
    M3ReviewProtocol,
    canonical_json,
    project_path,
)
from shaiwei.research.m3_multi_pool_review_evidence import (
    decide_reviews,
    expected_schedule,
    verify_empty_ledgers,
)
from shaiwei.research.m3_multi_pool_review_release import M3ReviewRelease
from shaiwei.research.m3_multi_pool_review_request import (
    plan_review,
    preflight,
    validate_review_document,
)


def _review_document(candidate_id: str, role: str) -> dict[str, object]:
    return {
        "schema_version": "m3-adversarial-review-response-v1",
        "candidate_id": candidate_id,
        "role": role,
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": (
            "No blocking construct issue is identified for the exact frozen expression "
            "within this narrowly assigned review role."
        ),
        "findings": [
            {
                "severity": "minor",
                "category": "conditional_mechanism",
                "statement": (
                    "The exact frozen claim remains conditional on its stated market mechanism."
                ),
                "falsification_or_resolution": (
                    "Keep the frozen expression unchanged and test only under a later frozen protocol."
                ),
            }
        ],
        "formula_change_or_new_candidate_proposed": False,
        "performance_claim_made": False,
    }


def _decision_rows(*, blocked: tuple[str, ...] = ()) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ordinal, candidate_id, role in expected_schedule():
        is_blocked = candidate_id in blocked and role == "construct_and_units"
        rows.append(
            {
                "review_ordinal": str(ordinal),
                "candidate_id": candidate_id,
                "role": role,
                "schema_status": "PASS",
                "semantic_status": PASS,
                "role_verdict": "BLOCKER_FOUND" if is_blocked else "NO_BLOCKER_FOUND",
            }
        )
    return rows


def _fixture_checks(protocol: M3ReviewProtocol) -> dict[str, bool]:
    plan = plan_review(protocol, 1)
    valid = _review_document(plan.candidate.candidate_id, plan.role)
    _, semantic = validate_review_document(protocol, plan, valid)
    changed = json.loads(json.dumps(valid))
    changed["findings"][0]["falsification_or_resolution"] = (
        "Replace the formula with a normalized alternative before validation."
    )
    _, changed_semantic = validate_review_document(protocol, plan, changed)
    one_blocked = decide_reviews(_decision_rows(blocked=(CANDIDATE_IDS[0],)))
    both_blocked = decide_reviews(_decision_rows(blocked=CANDIDATE_IDS))
    invalid = _decision_rows()
    invalid[3]["semantic_status"] = "MANUAL_REVIEW_REQUIRED"
    return {
        "strict_schema_and_semantic_pass": semantic.status == PASS,
        "free_text_formula_change_fails": changed_semantic.status == FAIL,
        "one_candidate_pass_allows_protocol_freeze_only": one_blocked[1]
        == "GO_FREEZE_M3_4_VALIDATION_PROTOCOL_ONLY",
        "both_candidates_blocked_stop_family": both_blocked[1]
        == "STOP_M3_FAMILY_BEFORE_VALIDATION",
        "one_invalid_response_stops_batch": decide_reviews(invalid)
        == ({}, "STOP_M3_3_REVIEW_CONTRACT"),
    }


def run_preexecution(
    protocol_path: Path = DEFAULT_PROTOCOL_PATH,
    release_path: Path = DEFAULT_RELEASE_PATH,
) -> dict[str, object]:
    protocol = M3ReviewProtocol.load(protocol_path)
    release = M3ReviewRelease.load(release_path, protocol)
    contract = preflight(protocol_path)
    fixtures = _fixture_checks(protocol)
    if not all(fixtures.values()):
        raise D1ControlError("M3-3 disconnected fixture failed")
    ledger_config = release.document["ledgers"]
    ledger_counts = verify_empty_ledgers(
        project_path(ledger_config["review"], label="review ledger"),
        project_path(ledger_config["transport"], label="transport ledger"),
    )
    return {
        "schema_version": "m3-multi-pool-review-preexecution-report-v1",
        **contract,
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "code_bundle_sha256": release.code_bundle_sha256,
        "runtime_code_snapshot_sha256": code_snapshot_sha256(),
        "runtime_git_head": git_head(),
        "image_tag": release.image_tag,
        "fixture_checks": fixtures,
        "ledger_counts": ledger_counts,
        "api_key_read": False,
        "provider_calls": 0,
        "review_results_inspected": False,
        "discovery_metric_fields_parsed": False,
        "sealed_validation_read": False,
        "g1_model_backtest_signal_run": False,
        "execution_authorized": False,
        "future_live_requires_explicit_user_authority": True,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "preexecution_gate": "GO_M3_3_PREEXECUTION_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--execution-release", type=Path, default=DEFAULT_RELEASE_PATH)
    args = parser.parse_args(argv)
    try:
        report = run_preexecution(args.protocol, args.execution_release)
    except (D1ControlError, OSError, TypeError, ValueError):
        print(canonical_json({"preexecution_gate": "FAIL", "error_class": "M3ReviewGateError"}))
        return 2
    print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
