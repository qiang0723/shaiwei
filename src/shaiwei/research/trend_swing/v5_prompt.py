"""Offline request planning for a separately authorized TS-v5 DeepSeek batch."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal, Mapping

from pydantic import ValidationError

from shaiwei.research.trend_swing.v5_contract import V5Bundle, canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_models import Mechanism, MechanismCandidate, candidate_schema

FORBIDDEN_KEYS = {
    "raw_market_rows",
    "security_identity",
    "security_list",
    "holdings",
    "orders",
    "sealed_validation",
    "locked_test",
    "forward_results",
    "production_signals",
    "api_key",
    "secret",
}


@dataclass(frozen=True)
class AttemptPlan:
    attempt_id: str
    ordinal: int
    mechanism: Mechanism
    mode: Literal["INDEPENDENT", "ADVERSARIAL_REVISION"]


def plan_attempt(bundle: V5Bundle, ordinal: int) -> AttemptPlan:
    total = int(bundle.prompt["attempt_schedule"]["total_completed_responses_exact"])
    if not 1 <= ordinal <= total:
        raise ValueError(f"TS-v5 ordinal must be within 1..{total}")
    mechanisms = bundle.mechanisms
    mode: Literal["INDEPENDENT", "ADVERSARIAL_REVISION"]
    if ordinal <= len(mechanisms):
        mechanism, mode = mechanisms[ordinal - 1], "INDEPENDENT"
    else:
        mechanism, mode = mechanisms[ordinal - len(mechanisms) - 1], "ADVERSARIAL_REVISION"
    identity = f"{bundle.identity()['prompt_sha256']}:{ordinal}:{mechanism}:{mode}"
    return AttemptPlan(sha256_text(identity)[:20], ordinal, mechanism, mode)


def _assert_safe_payload(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"TS-v5 request contains forbidden field: {key}")
            _assert_safe_payload(child)
    elif isinstance(value, list):
        for child in value:
            _assert_safe_payload(child)
    elif isinstance(value, str):
        if re.search(r"/(?:Users|private|workspace|etc|tmp)/", value):
            raise ValueError("TS-v5 request contains an absolute path")
        if re.search(r"\b\d{6}\.(?:SH|SZ|BJ)\b", value, re.IGNORECASE):
            raise ValueError("TS-v5 request contains a security identifier")
        if re.search(r"sk-[A-Za-z0-9]{8,}", value):
            raise ValueError("TS-v5 request contains a secret-shaped string")


def build_request(
    bundle: V5Bundle,
    plan: AttemptPlan,
    *,
    parent: MechanismCandidate | None = None,
    parent_attempt_fingerprint: str | None = None,
    parent_failure_class: str | None = None,
    discovery_feedback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if plan.mode == "INDEPENDENT" and (
        parent is not None
        or parent_attempt_fingerprint is not None
        or parent_failure_class is not None
        or discovery_feedback
    ):
        raise ValueError("independent TS-v5 attempts cannot receive prior feedback")
    if plan.mode == "ADVERSARIAL_REVISION":
        if parent_attempt_fingerprint is None or not re.fullmatch(
            r"[0-9a-f]{64}", parent_attempt_fingerprint
        ):
            raise ValueError("TS-v5 revision requires one bound parent-attempt fingerprint")
        if parent is not None and (
            parent.primary_mechanism != plan.mechanism
            or parent.fingerprint() != parent_attempt_fingerprint
            or parent_failure_class is not None
        ):
            raise ValueError("TS-v5 revision has an inconsistent same-mechanism parent")
        if parent is None and not parent_failure_class:
            raise ValueError("TS-v5 revision without a valid parent needs its failure class")
    allowed_feedback = set(bundle.prompt["feedback_contract"]["allowed_fields"])
    feedback = dict(discovery_feedback or {})
    if set(feedback) - allowed_feedback:
        raise ValueError("TS-v5 feedback contains non-allowlisted fields")
    task = {
        "attempt_id": plan.attempt_id,
        "ordinal": plan.ordinal,
        "mode": plan.mode,
        "primary_mechanism": plan.mechanism,
        "candidate_schema": candidate_schema(),
        "product_constraints": bundle.governance["product_constraints"],
        "candidate_limits": bundle.governance["candidate_contract"],
        "public_knowledge_summary": bundle.prompt["public_knowledge_summary"],
        "frozen_failure_memory": bundle.prompt["frozen_failure_memory"],
        "parent_candidate": parent.model_dump(mode="json") if parent else None,
        "parent_attempt": (
            {
                "fingerprint": parent_attempt_fingerprint,
                "status": "VALID_CANDIDATE" if parent else "INVALID_RESPONSE_COUNTED",
                "failure_class": parent_failure_class,
                "raw_response_included": False,
            }
            if parent_attempt_fingerprint
            else None
        ),
        "discovery_feedback": feedback,
        "instructions": {
            "one_primary_mechanism_only": True,
            "logic_revision_not_parameter_optimization": True,
            "return_json_only": True,
            "no_best_parameter_or_performance_claim": True,
        },
    }
    request = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": bundle.system_prompt},
            {"role": "user", "content": canonical_json(task)},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "max_tokens": 1800,
        "tools": [],
        "stream": False,
    }
    _assert_safe_payload(request)
    if len(canonical_json(request).encode("utf-8")) > 48_000:
        raise ValueError("TS-v5 request exceeds its conservative byte bound")
    return request


def validate_response(
    plan: AttemptPlan,
    document: Mapping[str, Any],
    *,
    expected_parent_fingerprint: str | None = None,
) -> MechanismCandidate:
    try:
        candidate = MechanismCandidate.model_validate(document)
    except ValidationError as exc:
        raise ValueError("TS-v5 candidate response violates the strict schema") from exc
    if candidate.primary_mechanism != plan.mechanism or candidate.lineage.mode != plan.mode:
        raise ValueError("TS-v5 response identity differs from the planned attempt")
    expected_parents = [] if expected_parent_fingerprint is None else [expected_parent_fingerprint]
    if candidate.lineage.parent_candidate_fingerprints != expected_parents:
        raise ValueError("TS-v5 response lineage differs from the bound parent attempt")
    return candidate


def preflight() -> dict[str, Any]:
    bundle = V5Bundle.load()
    independent_requests = [
        build_request(bundle, plan_attempt(bundle, ordinal)) for ordinal in range(1, 7)
    ]
    request_hashes = [sha256_text(canonical_json(request)) for request in independent_requests]
    return {
        **bundle.identity(),
        "family_status": bundle.governance["family"]["family_status"],
        "mechanism_count": len(bundle.mechanisms),
        "planned_completed_responses_exact": 12,
        "independent_request_count_prepared": len(independent_requests),
        "independent_request_hashes": request_hashes,
        "request_bundle_sha256": sha256_text(canonical_json(independent_requests)),
        "maximum_cost_usd": bundle.governance["llm_boundary"]["suggested_first_batch"][
            "maximum_cost_usd"
        ],
        "provider_calls": 0,
        "market_or_effect_rows_read": 0,
        "secret_read": False,
        "live_research_authorized": False,
        "preflight_gate": "PASS",
    }
