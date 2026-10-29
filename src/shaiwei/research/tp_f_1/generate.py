"""TP-F-1 stage G: one serial generation batch under the frozen budget, candidate contract and blind packet."""

from __future__ import annotations

from contextlib import AbstractContextManager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from shaiwei.ledger import append_llm_factor_attempt, portable_artifact_path, sha256_file
from shaiwei.research.provider_contract import ProviderResponse
from shaiwei.research.tp_f_0b.signature import SignatureRule
from shaiwei.research.tp_f_1.candidate import IdentityIndex, validate_candidate
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope
from shaiwei.research.tp_f_1.prompt import PromptBundle, canonical_json, parse_response
from shaiwei.research.tp_f_1.review import blind_packet
from shaiwei.research.tp_f_1.transport import OPERATOR, Prices

ATTEMPT_HEADER = (
    "attempt_id", "ordinal", "completed_at", "scope_sha256", "protocol_sha256", "prompt_sha256", "request_sha256",
    "requested_model", "returned_model", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens",
    "estimated_cost_usd", "status", "candidate_id", "canonical_expression", "canonical_sha256",
    "decision_artifact_path", "decision_artifact_sha256", "operator",
)


class Provider(Protocol):
    def complete(self, request: dict[str, Any]) -> ProviderResponse: ...


def write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    payload = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise TPF1Error(f"TP-F-1 write-once output already exists: {path.name}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
    return hashlib.sha256(payload).hexdigest()


def run_generation(
    scope: TPF1Scope,
    prompt: PromptBundle,
    index: IdentityIndex,
    rule: SignatureRule,
    *,
    scope_sha256: str,
    provider_for: Callable[[str], AbstractContextManager[Provider]],
    prices: Prices,
    output_dir: Path,
    attempt_ledger: Path,
    append_attempt: Callable[..., bool] = append_llm_factor_attempt,
) -> dict[str, Any]:
    """Serial calls until 8 completed responses, 3 qualified candidates, or the next worst case would breach $1.

    `append_attempt` is the ledger write entry; only the in-image fixture injects a recorder, because a released runtime
    refuses locks on non-project ledger paths by design.
    """
    batch = scope.document["batch_contract"]
    try:
        output_dir.mkdir(parents=True, exist_ok=False)  # 排他认领：目录已在即同 scope 重跑
    except FileExistsError as exc:
        raise TPF1Error("TP-F-1 generation directory exists; same-scope rerun is forbidden") from exc
    write_json_once(output_dir / "generation_started.json", {"scope_sha256": scope_sha256, "prompt_sha256": prompt.sha256})
    ceiling = Decimal(str(batch["single_batch_hard_ceiling_usd"]))
    worst = prices.worst_case(int(prompt.document["request"]["maximum_prompt_tokens_per_attempt"]),
                              int(prompt.document["request"]["max_tokens"]))
    spent, seen, proposed = Decimal(0), set(), []
    attempts: list[dict[str, Any]] = []
    qualified: list[dict[str, Any]] = []
    stop_reason = "COMPLETED_RESPONSE_MAXIMUM"
    for ordinal in range(1, int(batch["completed_responses_maximum"]) + 1):
        if len(qualified) >= int(batch["qualified_candidates_maximum"]):
            stop_reason = "QUALIFIED_CANDIDATE_MAXIMUM"
            break
        if spent + worst > ceiling:
            stop_reason = "BUDGET_CEILING"
            break
        attempt_id = hashlib.sha256(f"{scope_sha256}|{ordinal}".encode()).hexdigest()[:16]
        request = prompt.build_request(ordinal=ordinal, already_proposed=proposed)
        with provider_for(attempt_id) as provider:
            response = provider.complete(request)
        if response.model != batch["model"]:
            raise TPF1Error(f"TP-F-1 provider returned another model: {response.model}; no substitution")
        cost = prices.cost(response.usage)
        spent += cost
        parsed = None if response.sensitive_output_detected else parse_response(response.content)
        if parsed is None:
            verdict: dict[str, Any] = {"status": "RESPONSE_SCHEMA"}
        else:
            verdict = validate_candidate(scope, index, rule, parsed[0], parsed[1], seen_in_batch=frozenset(seen))
            if verdict.get("canonical_sha256"):
                seen.add(verdict["canonical_sha256"])
            if verdict.get("normalized_expression"):
                proposed.append(verdict["normalized_expression"])
        candidate_id = verdict["canonical_sha256"][:12] if verdict["status"] == "QUALIFIED" else ""
        decision = {"attempt_id": attempt_id, "ordinal": ordinal, "request_sha256": hashlib.sha256(canonical_json(request).encode()).hexdigest(),
                    "response_source_sha256": response.source_response_sha256, "verdict": verdict, "candidate_id": candidate_id}
        decision_path = output_dir / "attempts" / f"{ordinal:02d}-{attempt_id}.json"
        decision_sha = write_json_once(decision_path, decision)
        usage = response.usage or {}
        row = {
            "attempt_id": attempt_id, "ordinal": str(ordinal), "completed_at": response.completed_at, "scope_sha256": scope_sha256,
            "protocol_sha256": scope.sha256, "prompt_sha256": prompt.sha256, "request_sha256": decision["request_sha256"],
            "requested_model": batch["model"], "returned_model": response.model,
            "prompt_cache_hit_tokens": str(usage.get("prompt_cache_hit_tokens", 0)),
            "prompt_cache_miss_tokens": str(usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0))),
            "completion_tokens": str(usage.get("completion_tokens", 0)), "estimated_cost_usd": f"{cost:.12f}",
            "status": verdict["status"], "candidate_id": candidate_id, "canonical_expression": verdict.get("canonical", ""),
            "canonical_sha256": verdict.get("canonical_sha256", ""), "decision_artifact_path": portable_artifact_path(decision_path),
            "decision_artifact_sha256": decision_sha, "operator": OPERATOR,
        }
        append_attempt(path=attempt_ledger, **row)
        attempts.append(row)
        if verdict["status"] == "QUALIFIED":
            qualified.append({"candidate_id": candidate_id, "canonical_expression": verdict["canonical"],
                              "normalized_expression": verdict["normalized_expression"],
                              "economic_rationale": verdict["economic_rationale"], "attempt_id": attempt_id})
    summary: dict[str, Any] = {
        "schema_version": "tp-f-1-generation-summary-v1", "scope_sha256": scope_sha256, "protocol_sha256": scope.sha256,
        "addendum_sha256": scope.addendum_sha256, "prompt_sha256": prompt.sha256, "completed_responses": len(attempts),
        "qualified_candidates": [item["candidate_id"] for item in qualified], "stop_reason": stop_reason,
        "spent_usd": f"{spent:.12f}", "single_batch_ceiling_usd": str(ceiling), "worst_case_per_attempt_usd": f"{worst:.12f}",
        "status_counts": {status: sum(row["status"] == status for row in attempts) for status in sorted({row["status"] for row in attempts})},
        "attempt_ids": [row["attempt_id"] for row in attempts], "identity_index_counts": index.source_counts,
        "market_data_read": False,
    }
    if qualified:
        write_json_once(output_dir / "qualified_candidates.json", {"scope_sha256": scope_sha256, "candidates": qualified})
        summary["blind_packet_sha256"] = write_json_once(output_dir / "blind_review_packet.json", blind_packet(scope_sha256, qualified))
    else:
        summary["verdict_if_no_candidate"] = "REJECT_TP_F_AND_CLOSE"
    summary["attempt_ledger_sha256"] = sha256_file(attempt_ledger)
    write_json_once(output_dir / "generation_summary.json", summary)
    return summary
