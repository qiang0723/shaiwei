"""Append-only TS-v5 response evidence and deterministic classification."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import append_ts_v5_llm_attempt, sha256_file
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_models import MechanismCandidate
from shaiwei.research.trend_swing.v5_prompt import AttemptPlan, validate_response
from shaiwei.research.trend_swing.v5_transport import V5ExecutionRelease, V5TransportProtocol

ATTEMPT_HEADER = (
    "attempt_id", "ordinal", "mode", "mechanism", "completed_at", "provider",
    "requested_model", "returned_model", "protocol_sha256", "execution_release_id",
    "execution_release_sha256", "request_sha256", "response_sha256", "code_snapshot_sha256",
    "prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens",
    "completion_tokens", "estimated_cost_usd", "parse_status", "schema_status",
    "duplicate_status", "candidate_fingerprint", "semantic_signature", "parent_fingerprint",
    "failure_class", "raw_artifact_path", "raw_artifact_sha256", "manifest_path",
    "manifest_sha256", "operator",
)


def write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable TS-v5 artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def attempt_rows(path: Path, release: V5ExecutionRelease) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if tuple(reader.fieldnames or ()) != ATTEMPT_HEADER:
        raise D1ControlError("TS-v5 attempt ledger schema differs")
    if len(rows) > 12 or len({row["attempt_id"] for row in rows}) != len(rows):
        raise D1ControlError("TS-v5 attempt ledger count or identity differs")
    if [int(row["ordinal"]) for row in rows] != list(range(1, len(rows) + 1)):
        raise D1ControlError("TS-v5 attempt ledger is not a contiguous prefix")
    if any(
        row["execution_release_id"] != release.release_id
        or row["execution_release_sha256"] != release.sha256
        for row in rows
    ):
        raise D1ControlError("TS-v5 attempt ledger release differs")
    return rows


def _usage_and_cost(
    protocol: V5TransportProtocol, response: ProviderResponse
) -> tuple[dict[str, int], float]:
    required = ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens")
    if not isinstance(response.usage, dict) or any(key not in response.usage for key in required):
        raise D1ControlError("provider usage is missing required fields")
    usage = {key: response.usage[key] for key in required}
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in usage.values()):
        raise D1ControlError("provider usage contains an invalid value")
    if usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"] != usage["prompt_tokens"]:
        raise D1ControlError("provider cache usage does not sum to prompt tokens")
    if usage["prompt_tokens"] > 16_000 or usage["completion_tokens"] > 1_800:
        raise D1ControlError("provider usage exceeds the approved per-response limits")
    cost = (
        usage["prompt_cache_hit_tokens"] * 0.003625
        + usage["prompt_cache_miss_tokens"] * 0.435
        + usage["completion_tokens"] * 0.87
    ) / 1_000_000
    return usage, cost


def classify_response(
    protocol: V5TransportProtocol,
    release: V5ExecutionRelease,
    plan: AttemptPlan,
    response: ProviderResponse,
    *,
    parent_fingerprint: str | None,
    prior_semantic_signatures: set[str],
) -> dict[str, Any]:
    try:
        usage, cost = _usage_and_cost(protocol, response)
    except D1ControlError:
        usage = {
            "prompt_tokens": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
            "completion_tokens": 0,
        }
        cost = (16_000 * 0.435 + 1_800 * 0.87) / 1_000_000
        usage_failure = "PROVIDER_USAGE_INVALID_WORST_CASE_RESERVED"
    else:
        usage_failure = ""
    candidate: MechanismCandidate | None = None
    parse_status = schema_status = "NOT_EVALUATED"
    duplicate_status = "NOT_EVALUATED"
    failure_class = usage_failure
    if not failure_class and response.model != release.response_model_identity:
        failure_class = "PROVIDER_MODEL_IDENTITY_MISMATCH"
    elif not failure_class and response.finish_reason != "stop":
        failure_class = "PROVIDER_FINISH_REASON_INVALID"
    elif not failure_class and response.sensitive_output_detected:
        failure_class = "PROVIDER_SENSITIVE_OUTPUT"
    if not failure_class:
        try:
            document = json.loads(response.content)
            parse_status = "PASS"
            candidate = validate_response(
                plan, document, expected_parent_fingerprint=parent_fingerprint
            )
            schema_status = "PASS"
            duplicate_status = (
                "DUPLICATE" if candidate.semantic_signature() in prior_semantic_signatures else "UNIQUE"
            )
            if duplicate_status == "DUPLICATE":
                failure_class = "SEMANTIC_DUPLICATE"
        except json.JSONDecodeError:
            parse_status, failure_class = "FAIL", "CANDIDATE_JSON_INVALID"
        except (TypeError, ValueError):
            parse_status = "PASS"
            schema_status, failure_class = "FAIL", "CANDIDATE_SCHEMA_INVALID"
    return {
        "usage": usage,
        "cost": cost,
        "candidate": candidate,
        "parse_status": parse_status,
        "schema_status": schema_status,
        "duplicate_status": duplicate_status,
        "failure_class": failure_class,
    }


def persist_completed_attempt(
    *,
    protocol: V5TransportProtocol,
    release: V5ExecutionRelease,
    plan: AttemptPlan,
    response: ProviderResponse,
    classified: dict[str, Any],
    request_sha: str,
    parent_fingerprint: str | None,
    raw_path: Path,
    attempt_path: Path,
    output_root: Path,
    code_sha: str,
    project_root: Path = PROJECT_ROOT,
) -> None:
    candidate = classified["candidate"]
    manifest = {
        "schema_version": "ts-v5-llm-attempt-manifest-v1",
        "attempt_id": plan.attempt_id,
        "ordinal": plan.ordinal,
        "mode": plan.mode,
        "mechanism": plan.mechanism,
        "request_sha256": request_sha,
        "response_sha256": response.source_response_sha256,
        "raw_artifact_sha256": sha256_file(raw_path),
        "candidate_fingerprint": candidate.fingerprint() if candidate else "",
        "semantic_signature": candidate.semantic_signature() if candidate else "",
        "parent_fingerprint": parent_fingerprint or "",
        "parse_status": classified["parse_status"],
        "schema_status": classified["schema_status"],
        "duplicate_status": classified["duplicate_status"],
        "failure_class": classified["failure_class"],
        "protocol_sha256": protocol.sha256,
        "execution_release_sha256": release.sha256,
    }
    manifest_path = output_root / "artifacts/manifests" / f"{plan.attempt_id}.json"
    write_once(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    usage = classified["usage"]
    row = {
        "attempt_id": plan.attempt_id,
        "ordinal": str(plan.ordinal),
        "mode": plan.mode,
        "mechanism": plan.mechanism,
        "completed_at": response.completed_at,
        "provider": protocol.provider_name,
        "requested_model": protocol.requested_model,
        "returned_model": response.model,
        "protocol_sha256": protocol.sha256,
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
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
        "duplicate_status": classified["duplicate_status"],
        "candidate_fingerprint": candidate.fingerprint() if candidate else "",
        "semantic_signature": candidate.semantic_signature() if candidate else "",
        "parent_fingerprint": parent_fingerprint or "",
        "failure_class": classified["failure_class"],
        "raw_artifact_path": raw_path.relative_to(project_root).as_posix(),
        "raw_artifact_sha256": sha256_file(raw_path),
        "manifest_path": manifest_path.relative_to(project_root).as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "operator": "docker-ts-v5-llm",
    }
    if not append_ts_v5_llm_attempt(path=attempt_path, **row):
        raise D1ControlError("TS-v5 attempt row unexpectedly exists")


def response_envelope(response: ProviderResponse) -> dict[str, Any]:
    return {
        "model": response.model,
        "content": response.content,
        "reasoning_content": response.reasoning_content,
        "finish_reason": response.finish_reason,
        "usage": response.usage,
        "completed_at": response.completed_at,
        "sensitive_output_detected": response.sensitive_output_detected,
        "source_response_sha256": response.source_response_sha256,
    }


def candidate_gate(rows: list[dict[str, str]]) -> tuple[str, int]:
    """Admit only a complete batch containing at least one usable candidate."""
    valid = sum(
        row["schema_status"] == "PASS"
        and row["duplicate_status"] == "UNIQUE"
        and not row["failure_class"]
        for row in rows
    )
    if len(rows) != 12:
        return "STOP_INCOMPLETE_BATCH", valid
    if valid == 0:
        return "STOP_NO_VALID_CANDIDATES", valid
    return "GO_CANDIDATES_ONLY", valid
