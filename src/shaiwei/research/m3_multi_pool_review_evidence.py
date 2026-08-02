"""Fail-closed evidence and terminal decision rules for M3-3 reviews."""

from __future__ import annotations

import csv
from pathlib import Path

from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import PASS as SEMANTIC_PASS
from shaiwei.research.m3_multi_pool_review_contract import CANDIDATE_IDS
from shaiwei.research.m3_multi_pool_review_schema import M3_REVIEW_ROLES


REVIEW_LEDGER_HEADER = (
    "review_id",
    "protocol_id",
    "execution_release_id",
    "execution_release_sha256",
    "candidate_id",
    "review_ordinal",
    "role",
    "completed_at",
    "provider",
    "requested_model",
    "returned_model",
    "protocol_sha256",
    "prompt_sha256",
    "request_sha256",
    "response_sha256",
    "code_snapshot_sha256",
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "estimated_cost_usd",
    "parse_status",
    "schema_status",
    "semantic_status",
    "semantic_reason_codes_json",
    "inspected_text_sha256",
    "role_verdict",
    "critical_findings",
    "major_findings",
    "minor_findings",
    "failure_class",
    "raw_artifact_path",
    "raw_artifact_sha256",
    "manifest_path",
    "manifest_sha256",
    "operator",
)


def verify_empty_ledgers(review_path: Path, transport_path: Path) -> dict[str, int]:
    """Require pristine, schema-bound ledgers before any live authorization exists."""
    counts: dict[str, int] = {}
    for label, path, header in (
        ("review", review_path, REVIEW_LEDGER_HEADER),
        ("transport", transport_path, TRANSPORT_LEDGER_HEADER_V2),
    ):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        if tuple(reader.fieldnames or ()) != header:
            raise D1ControlError(f"M3-3 {label} ledger schema differs")
        if rows:
            raise D1ControlError(f"M3-3 {label} ledger must be empty before live authorization")
        counts[f"{label}_rows"] = 0
    return counts


def expected_schedule() -> tuple[tuple[int, str, str], ...]:
    return tuple(
        (ordinal, CANDIDATE_IDS[(ordinal - 1) // 4], M3_REVIEW_ROLES[(ordinal - 1) % 4])
        for ordinal in range(1, 9)
    )


def decide_reviews(rows: list[dict[str, str]]) -> tuple[dict[str, str], str]:
    """Apply the frozen negative-screen rule without reading review narratives."""
    actual_schedule: list[tuple[int, str, str]] = []
    try:
        actual_schedule = [
            (int(row["review_ordinal"]), row["candidate_id"], row["role"]) for row in rows
        ]
    except (KeyError, TypeError, ValueError):
        pass
    all_valid = (
        len(rows) == 8
        and tuple(actual_schedule) == expected_schedule()
        and all(
            row.get("schema_status") == "PASS"
            and row.get("semantic_status") == SEMANTIC_PASS
            and row.get("role_verdict") in {"NO_BLOCKER_FOUND", "BLOCKER_FOUND"}
            for row in rows
        )
    )
    if not all_valid:
        return {}, "STOP_M3_3_REVIEW_CONTRACT"
    decisions: dict[str, str] = {}
    for candidate_id in CANDIDATE_IDS:
        candidate_rows = [row for row in rows if row["candidate_id"] == candidate_id]
        decisions[candidate_id] = (
            "PASS_REVIEW"
            if all(row["role_verdict"] == "NO_BLOCKER_FOUND" for row in candidate_rows)
            else "REJECT_REVIEW_BLOCKER"
        )
    gate = (
        "GO_FREEZE_M3_4_VALIDATION_PROTOCOL_ONLY"
        if "PASS_REVIEW" in decisions.values()
        else "STOP_M3_FAMILY_BEFORE_VALIDATION"
    )
    return decisions, gate
