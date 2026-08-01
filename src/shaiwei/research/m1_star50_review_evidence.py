"""Immutable evidence verification and terminal decision for M1-2 reviews."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from shaiwei.ledger import sha256_file
from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import PASS as SEMANTIC_PASS
from shaiwei.research.m1_star50_review_contract import (
    CANDIDATE_IDS,
    M1ReviewProtocol,
    project_path,
)
from shaiwei.research.m1_star50_review_release import M1ReviewRelease


def verify_static_evidence(
    rows: list[dict[str, str]],
    transport_path: Path,
    output_root: Path,
    release: M1ReviewRelease,
) -> dict[str, int]:
    ordinals = [int(row["review_ordinal"]) for row in rows]
    if not rows or ordinals != list(range(1, len(rows) + 1)) or len(rows) > 8:
        raise D1ControlError("M1-2 review rows are not a valid prefix")
    for row in rows:
        if (
            row["execution_release_id"] != release.release_id
            or row["execution_release_sha256"] != release.sha256
        ):
            raise D1ControlError("M1-2 review row release differs")
        request = output_root / "artifacts/requests" / (
            f"{row['review_id']}-{row['request_sha256'][:12]}.json"
        )
        raw = project_path(row["raw_artifact_path"], label="raw review artifact")
        manifest = project_path(row["manifest_path"], label="review manifest")
        if (
            sha256_file(request) != row["request_sha256"]
            or sha256_file(raw) != row["raw_artifact_sha256"]
            or sha256_file(manifest) != row["manifest_sha256"]
        ):
            raise D1ControlError("M1-2 immutable artifact hash differs")
    with transport_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
            raise D1ControlError("M1-2 transport ledger schema differs")
        events = list(reader)
    completed = [event for event in events if event["event_type"] == "COMPLETED"]
    if len(completed) != len(rows) or any(
        event["execution_release_id"] != release.release_id
        or event["execution_release_sha256"] != release.sha256
        for event in events
    ):
        raise D1ControlError("M1-2 transport evidence differs")
    provider_root = (output_root / "artifacts/provider").resolve()
    for event in completed:
        candidate = (provider_root / event["response_artifact_path"]).resolve()
        if not candidate.is_relative_to(provider_root) or sha256_file(candidate) != event[
            "response_artifact_sha256"
        ]:
            raise D1ControlError("M1-2 provider artifact differs")
    return {
        "review_rows": len(rows),
        "request_artifacts": len(rows),
        "raw_response_artifacts": len(rows),
        "review_manifests": len(rows),
        "provider_response_artifacts": len(completed),
        "transport_events": len(events),
        "transport_completions": len(completed),
    }


def build_terminal_report(
    *,
    protocol: M1ReviewProtocol,
    release: M1ReviewRelease,
    rows: list[dict[str, str]],
    transport_path: Path,
    output_root: Path,
    code_sha: str,
    tls_sha: str,
) -> dict[str, Any]:
    static = verify_static_evidence(rows, transport_path, output_root, release)
    decisions, gate = decide_reviews(rows)
    return {
        "schema_version": "m1-star50-factor-review-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "prompt_sha256": protocol.prompt_sha256,
        "semantic_protocol_sha256": protocol.semantic_protocol.sha256,
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "implementation_git_head": release.implementation_git_head,
        "code_snapshot_sha256": code_sha,
        "completed_response_count": len(rows),
        "completed_response_exact_gate": len(rows) == 8,
        "schema_and_semantic_valid_count": sum(
            row["schema_status"] == "PASS" and row["semantic_status"] == SEMANTIC_PASS
            for row in rows
        ),
        "role_verdict_counts": {
            value: sum(row["role_verdict"] == value for row in rows)
            for value in ("NO_BLOCKER_FOUND", "BLOCKER_FOUND")
        },
        "failure_class_counts": {
            value or "NONE": sum(row["failure_class"] == value for row in rows)
            for value in sorted({row["failure_class"] for row in rows})
        },
        "candidate_decisions": decisions,
        "actual_cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows),
        "review_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "reviewers_result_blind": True,
        "primary_window_contamination_recorded": True,
        "new_candidates_generated": False,
        "sealed_validation_read": False,
        "stress_or_g1_run": False,
        "model_or_portfolio_run": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "review_gate": gate,
        "tls_certificate_sha256": tls_sha,
        "static_evidence": static,
    }


def decide_reviews(rows: list[dict[str, str]]) -> tuple[dict[str, str], str]:
    """Apply the frozen negative-screen rule without inspecting review narratives."""
    all_valid = len(rows) == 8 and all(
        row["schema_status"] == "PASS" and row["semantic_status"] == SEMANTIC_PASS
        for row in rows
    )
    decisions: dict[str, str] = {}
    if all_valid:
        for candidate_id in CANDIDATE_IDS:
            candidate_rows = [row for row in rows if row["candidate_id"] == candidate_id]
            decisions[candidate_id] = (
                "PASS_REVIEW"
                if len(candidate_rows) == 4
                and all(row["role_verdict"] == "NO_BLOCKER_FOUND" for row in candidate_rows)
                else "REJECT_REVIEW_BLOCKER"
            )
    if not all_valid:
        gate = "STOP_M1_2_REVIEW_CONTRACT"
    elif any(value == "PASS_REVIEW" for value in decisions.values()):
        gate = "GO_FREEZE_M1_3_VALIDATION_PROTOCOL_ONLY"
    else:
        gate = "STOP_M1_FAMILY_BEFORE_VALIDATION"
    return decisions, gate
