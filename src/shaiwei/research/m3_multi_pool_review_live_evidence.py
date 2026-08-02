"""Immutable artifacts, ledger checks and sanitized report for M3-3 live reviews."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import append_llm_factor_review, sha256_file
from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.llm_factor import D1ControlError, ProviderResponse
from shaiwei.research.llm_review_semantics import PASS as SEMANTIC_PASS
from shaiwei.research.m3_multi_pool_review_contract import (
    M3ReviewProtocol,
    ReviewPlan,
    canonical_json,
    project_path,
    sha256_text,
)
from shaiwei.research.m3_multi_pool_review_evidence import (
    REVIEW_LEDGER_HEADER,
    decide_reviews,
    expected_schedule,
)
from shaiwei.research.m3_multi_pool_review_live_release import M3ReviewLiveRelease


def write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable M3-3 artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def review_rows(path: Path, release: M3ReviewLiveRelease) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if tuple(reader.fieldnames or ()) != REVIEW_LEDGER_HEADER:
        raise D1ControlError("M3-3 review ledger schema differs")
    ids = [row["review_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise D1ControlError("M3-3 review ledger contains duplicate ids")
    if len(rows) > 8 or any(
        row["execution_release_id"] != release.release_id
        or row["execution_release_sha256"] != release.sha256
        for row in rows
    ):
        raise D1ControlError("M3-3 review ledger release or budget differs")
    actual = tuple(
        (int(row["review_ordinal"]), row["candidate_id"], row["role"]) for row in rows
    )
    if actual != expected_schedule()[: len(rows)]:
        raise D1ControlError("M3-3 review ledger is not the frozen contiguous prefix")
    return rows


def finding_counts(review: Any | None) -> dict[str, int]:
    return {
        severity: sum(item.severity == severity for item in review.findings) if review else 0
        for severity in ("critical", "major", "minor")
    }


def persist_completed_review(
    *,
    protocol: M3ReviewProtocol,
    release: M3ReviewLiveRelease,
    plan: ReviewPlan,
    response: ProviderResponse,
    classified: dict[str, Any],
    request_sha: str,
    raw_path: Path,
    code_sha: str,
    review_path: Path,
    output_root: Path,
) -> None:
    review = classified["review"]
    counts = finding_counts(review)
    manifest = {
        "schema_version": "m3-multi-pool-review-artifact-manifest-v1",
        "review_id": plan.review_id,
        "candidate_id": plan.candidate.candidate_id,
        "review_ordinal": plan.review_ordinal,
        "role": plan.role,
        "request_sha256": request_sha,
        "response_sha256": response.source_response_sha256,
        "raw_artifact_sha256": sha256_file(raw_path),
        "parse_status": classified["parse_status"],
        "schema_status": classified["schema_status"],
        "semantic_status": classified["semantic_status"],
        "semantic_reason_codes": classified["semantic_reason_codes"],
        "inspected_text_sha256": classified["inspected_text_sha256"],
        "role_verdict": review.role_verdict if review else "",
        "finding_counts": counts,
        "failure_class": classified["failure_class"],
        "protocol_sha256": protocol.sha256,
        "execution_release_sha256": release.sha256,
    }
    manifest_path = output_root / "artifacts/manifests" / f"{plan.review_id}.json"
    write_once(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    usage = classified["usage"]
    row = {
        "review_id": plan.review_id,
        "protocol_id": protocol.document["protocol_id"],
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "candidate_id": plan.candidate.candidate_id,
        "review_ordinal": str(plan.review_ordinal),
        "role": plan.role,
        "completed_at": response.completed_at,
        "provider": protocol.document["provider"]["provider"],
        "requested_model": protocol.requested_model,
        "returned_model": response.model,
        "protocol_sha256": protocol.sha256,
        "prompt_sha256": protocol.prompt_sha256,
        "request_sha256": request_sha,
        "response_sha256": response.source_response_sha256,
        "code_snapshot_sha256": code_sha,
        "prompt_tokens": str(usage["prompt_tokens"]),
        "prompt_cache_hit_tokens": str(usage["prompt_cache_hit_tokens"]),
        "prompt_cache_miss_tokens": str(usage["prompt_cache_miss_tokens"]),
        "completion_tokens": str(usage["completion_tokens"]),
        "estimated_cost_usd": f"{classified['cost']:.12f}",
        "parse_status": classified["parse_status"],
        "schema_status": classified["schema_status"],
        "semantic_status": classified["semantic_status"],
        "semantic_reason_codes_json": canonical_json(classified["semantic_reason_codes"]),
        "inspected_text_sha256": classified["inspected_text_sha256"],
        "role_verdict": review.role_verdict if review else "",
        "critical_findings": str(counts["critical"]),
        "major_findings": str(counts["major"]),
        "minor_findings": str(counts["minor"]),
        "failure_class": classified["failure_class"],
        "raw_artifact_path": raw_path.relative_to(PROJECT_ROOT).as_posix(),
        "raw_artifact_sha256": sha256_file(raw_path),
        "manifest_path": manifest_path.relative_to(PROJECT_ROOT).as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "operator": "docker-m3-multi-pool-review",
    }
    if not append_llm_factor_review(path=review_path, **row):
        raise D1ControlError("M3-3 review row unexpectedly exists")


def verify_static_evidence(
    rows: list[dict[str, str]],
    transport_path: Path,
    output_root: Path,
    release: M3ReviewLiveRelease,
) -> dict[str, int]:
    if not rows or len(rows) > 8:
        raise D1ControlError("M3-3 terminal evidence requires a nonempty valid prefix")
    for row in rows:
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
            raise D1ControlError("M3-3 immutable review artifact hash differs")
    with transport_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        events = list(reader)
    if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
        raise D1ControlError("M3-3 transport ledger schema differs")
    if any(
        event["execution_release_id"] != release.release_id
        or event["execution_release_sha256"] != release.sha256
        for event in events
    ):
        raise D1ControlError("M3-3 transport release differs")
    completed = [event for event in events if event["event_type"] == "COMPLETED"]
    completed_by_attempt = {event["attempt_id"]: event for event in completed}
    if len(completed) != len(rows) or len(completed_by_attempt) != len(completed):
        raise D1ControlError("M3-3 completed transport evidence differs")
    provider_root = (output_root / "artifacts/provider").resolve()
    for row in rows:
        event = completed_by_attempt.get(row["review_id"])
        if event is None or event["request_sha256"] != row["request_sha256"]:
            raise D1ControlError("M3-3 transport request identity differs")
        artifact = (provider_root / event["response_artifact_path"]).resolve()
        if (
            not artifact.is_relative_to(provider_root)
            or sha256_file(artifact) != event["response_artifact_sha256"]
            or event["source_response_sha256"] != row["response_sha256"]
        ):
            raise D1ControlError("M3-3 provider response evidence differs")
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
    protocol: M3ReviewProtocol,
    release: M3ReviewLiveRelease,
    rows: list[dict[str, str]],
    transport_path: Path,
    output_root: Path,
    code_sha: str,
    tls_sha: str,
) -> dict[str, Any]:
    static = verify_static_evidence(rows, transport_path, output_root, release)
    decisions, gate = decide_reviews(rows)
    response_bundle = [
        {
            "review_id": row["review_id"],
            "response_sha256": row["response_sha256"],
            "manifest_sha256": row["manifest_sha256"],
        }
        for row in rows
    ]
    return {
        "schema_version": "m3-multi-pool-factor-review-report-v1",
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
        "cost_gate_pass": sum(float(row["estimated_cost_usd"]) for row in rows)
        <= release.batch_hard_ceiling_usd,
        "response_evidence_bundle_sha256": sha256_text(canonical_json(response_bundle)),
        "reviewers_result_blind": True,
        "primary_controller_narratives_inspected": False,
        "primary_window_contamination_recorded": True,
        "new_candidates_generated": False,
        "formula_or_direction_changed": False,
        "replacement_candidate_used": False,
        "sealed_validation_read": False,
        "stress_or_g1_run": False,
        "model_backtest_portfolio_or_signal_run": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "m3_4_validation_protocol_freeze_allowed": gate
        == "GO_FREEZE_M3_4_VALIDATION_PROTOCOL_ONLY",
        "review_gate": gate,
        "tls_certificate_sha256": tls_sha,
        "static_evidence": static,
    }


def load_terminal_report(
    path: Path,
    *,
    rows: list[dict[str, str]],
    transport_path: Path,
    output_root: Path,
    release: M3ReviewLiveRelease,
) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise D1ControlError("M3-3 terminal report is invalid") from error
    if report.get("static_evidence") != verify_static_evidence(
        rows, transport_path, output_root, release
    ):
        raise D1ControlError("M3-3 terminal report evidence differs")
    if report.get("execution_release_sha256") != release.sha256:
        raise D1ControlError("M3-3 terminal report release differs")
    return report
