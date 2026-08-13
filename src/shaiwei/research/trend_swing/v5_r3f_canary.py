"""Zero-call preflight and v3 response classification for TS-v5-R3F."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_bound_proposal_contract import (
    CONTRACT_SHA256,
    BoundProposalContract,
    build_request_v4,
    compile_bound_proposal,
    independent_authority,
)
from shaiwei.research.trend_swing.v5_contract import (
    V5Bundle,
    canonical_json,
    sha256_file,
    sha256_text,
)
from shaiwei.research.trend_swing.v5_evidence import usage_and_cost, write_once
from shaiwei.research.trend_swing.v5_models import Mechanism, MechanismCandidate
from shaiwei.research.trend_swing.v5_response_contract import (
    CONTRACT_SHA256 as TERMINAL_CONTRACT_SHA256,
    V5ResponseContract,
)

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3f_llm_canary_scope_v1.yaml"
SCOPE_SHA256 = "1a45898caa3c4fac0c7a1b8a301271d48c3b0a666e947d7b988bd50d7e7aee61"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3f-canary-001"
REPORT_PATH = OUTPUT_ROOT / "preflight_report.json"
MECHANISMS = tuple(Mechanism)
WORST_CASE_SLOT_USD = (
    Decimal(16_000) * Decimal("0.435") + Decimal(1_800) * Decimal("0.87")
) / Decimal(1_000_000)


@dataclass(frozen=True)
class R3FTransportProtocol:
    """No-retry adapter over the existing audited DeepSeek transport."""

    bundle: V5Bundle
    document: dict[str, Any]
    sha256: str
    provider_name: str = "deepseek"
    requested_model: str = "deepseek-v4-pro"
    returned_model_identity: str = "DeepSeek-V4-Pro"

    @classmethod
    def load(cls) -> "R3FTransportProtocol":
        bundle = V5Bundle.load()
        document = {
            "provider": {
                "base_url": "https://api.deepseek.com",
                "request_timeout_seconds": 120,
            },
            "attempt_budget": {"maximum_transport_retries_per_attempt": 0},
        }
        identity = {**bundle.identity(), "transport": document}
        return cls(bundle, document, sha256_text(canonical_json(identity)))


@dataclass(frozen=True)
class R3FCanaryScope:
    document: dict[str, Any]
    sha256: str
    completed_responses: int = 6
    hard_ceiling_usd: Decimal = Decimal("0.15")

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "R3FCanaryScope":
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(PROJECT_ROOT.resolve(strict=True))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise D1ControlError("TS-v5-R3F scope is missing or outside the project") from exc
        if path.is_symlink() or sha256_file(resolved) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R3F scope identity differs")
        try:
            document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R3F scope is invalid") from exc
        cls._validate(document)
        return cls(document, SCOPE_SHA256)

    @staticmethod
    def _validate(document: Any) -> None:
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R3F scope must be an object")
        attempts = document.get("attempt_contract", {})
        provider = document.get("provider_contract", {})
        identity = document.get("frozen_identity", {})
        approval = document.get("user_approval", {}).get("bounded_interpretation", {})
        expected_order = [mechanism.value for mechanism in MECHANISMS]
        if (
            document.get("schema_version") != "ts-v5-r3f-llm-canary-scope-v1"
            or document.get("status") != "USER_APPROVED_RESULT_BEFORE_SCOPE_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("user_approval_received") is not True
            or document.get("deepseek_api_called") is not False
            or document.get("production_authorization") != "none"
            or identity.get("bound_proposal_contract_sha256") != CONTRACT_SHA256
            or identity.get("response_terminal_contract_sha256") != TERMINAL_CONTRACT_SHA256
            or identity.get("no_retry_transport_protocol_sha256") != R3FTransportProtocol.load().sha256
            or provider.get("thinking") != "disabled"
            or provider.get("maximum_output_tokens_per_response") != 1800
            or attempts.get("completed_response_target_exact") != 6
            or attempts.get("mechanism_order") != expected_order
            or attempts.get("maximum_transport_attempts_per_slot") != 1
            or attempts.get("transport_retry_authorized") is not False
            or attempts.get("external_request_maximum") != 6
            or attempts.get("replacement_response_authorized") is not False
            or approval.get("external_request_maximum") != 6
            or approval.get("replacement_or_seventh_response_authorized") is not False
        ):
            raise D1ControlError("TS-v5-R3F scope broadens or differs")
        cost = document.get("cost_contract", {})
        planned = WORST_CASE_SLOT_USD * Decimal(6)
        if (
            planned != Decimal(str(cost.get("planned_worst_case_all_cache_miss_usd")))
            or planned != Decimal("0.051156")
            or Decimal(str(cost.get("batch_hard_ceiling_usd"))) != Decimal("0.15")
            or planned >= Decimal(str(cost.get("batch_hard_ceiling_usd")))
        ):
            raise D1ControlError("TS-v5-R3F cost contract differs")


def attempt_id(mechanism: Mechanism, ordinal: int) -> str:
    return f"ts-v5-r3f-i{ordinal:02d}-{mechanism.value.lower().replace('_', '-')}"


def request_bundle() -> list[dict[str, Any]]:
    contract = BoundProposalContract.load()
    return [
        build_request_v4(
            mechanism,
            independent_authority(attempt_id(mechanism, ordinal), ordinal),
            contract=contract,
        )
        for ordinal, mechanism in enumerate(MECHANISMS, start=1)
    ]


def classify_proposal_response(
    mechanism: Mechanism,
    ordinal: int,
    response: ProviderResponse,
    *,
    prior_semantic_signatures: set[str] | None = None,
) -> dict[str, Any]:
    protocol = R3FTransportProtocol.load()
    try:
        usage, cost = usage_and_cost(protocol, response)  # type: ignore[arg-type]
    except D1ControlError:
        usage = {key: 0 for key in (
            "prompt_tokens", "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens", "completion_tokens",
        )}
        cost, failure = float(WORST_CASE_SLOT_USD), "PROVIDER_USAGE_INVALID_WORST_CASE_RESERVED"
    else:
        failure = ""
    candidate: MechanismCandidate | None = None
    parse_status = schema_status = duplicate_status = "NOT_EVALUATED"
    if not failure and response.model != "deepseek-v4-pro":
        failure = "PROVIDER_MODEL_IDENTITY_MISMATCH"
    elif not failure and response.sensitive_output_detected:
        failure = "PROVIDER_SENSITIVE_OUTPUT"
    elif not failure:
        failure = V5ResponseContract.load().terminal_failure(response)
    if not failure:
        try:
            document = json.loads(response.content)
            parse_status = "PASS"
            if not isinstance(document, dict):
                raise TypeError("proposal response must be an object")
            compiled = compile_bound_proposal(
                mechanism,
                document,
                independent_authority(attempt_id(mechanism, ordinal), ordinal),
            )
            if compiled.evidence_mode() != "INDEPENDENT":
                raise D1ControlError("TS-v5-R3F compiled evidence mode differs")
            candidate = compiled.candidate
            schema_status = "PASS"
            duplicate_status = (
                "DUPLICATE"
                if candidate.semantic_signature() in (prior_semantic_signatures or set())
                else "UNIQUE"
            )
            if duplicate_status == "DUPLICATE":
                failure = "SEMANTIC_DUPLICATE"
        except json.JSONDecodeError:
            parse_status, failure = "FAIL", "PROPOSAL_JSON_INVALID"
        except (D1ControlError, TypeError, ValueError):
            parse_status, schema_status = "PASS", "FAIL"
            failure = "BOUND_PROPOSAL_SCHEMA_OR_COMPILER_INVALID"
    return {
        "usage": usage,
        "cost": cost,
        "candidate": candidate,
        "parse_status": parse_status,
        "schema_status": schema_status,
        "duplicate_status": duplicate_status,
        "failure_class": failure,
    }


def batch_gate(completed_count: int, valid_unique_count: int) -> str:
    if completed_count != 6:
        return "STOP_INCOMPLETE_BATCH"
    if valid_unique_count == 6:
        return "GO_BOUND_PROPOSAL_CANARY_ONLY"
    if valid_unique_count >= 4:
        return "STOP_PARTIAL_BOUND_CONTRACT_COMPLIANCE"
    if valid_unique_count >= 1:
        return "STOP_WEAK_BOUND_CONTRACT_COMPLIANCE"
    return "STOP_NO_VALID_CANDIDATES"


def preflight() -> dict[str, Any]:
    scope, requests = R3FCanaryScope.load(), request_bundle()
    tasks = [json.loads(request["messages"][1]["content"]) for request in requests]
    request_hashes = [sha256_text(canonical_json(request)) for request in requests]
    schema_texts = [canonical_json(task["proposal_schema"]) for task in tasks]
    checks = {
        "request_count_exact": len(requests) == scope.completed_responses,
        "mechanism_order_exact": [
            task["mechanism_projection"]["primary_mechanism"] for task in tasks
        ] == [item.value for item in MECHANISMS],
        "authority_bound_independent": all(
            task["assigned_attempt_authority"]["mode"] == "INDEPENDENT"
            and task["assigned_attempt_authority"]["parent_candidate_fingerprints"] == []
            for task in tasks
        ),
        "response_schema_excludes_local_fields": all(
            '"lineage"' not in text and "search_points_maximum" not in text
            for text in schema_texts
        ),
        "request_hashes_unique": len(set(request_hashes)) == 6,
        "each_request_below_48kb": all(
            len(canonical_json(request).encode("utf-8")) <= 48_000 for request in requests
        ),
        "no_retry_protocol": R3FTransportProtocol.load().document[
            "attempt_budget"
        ]["maximum_transport_retries_per_attempt"] == 0,
        "all_batch_gates_enumerated": all(batch_gate(6, count) for count in range(7)),
        "user_authority_exact": scope.document["execution_authorized"] is True,
    }
    report = {
        "schema_version": "ts-v5-r3f-canary-preflight-v1",
        "scope_sha256": scope.sha256,
        "transport_protocol_sha256": R3FTransportProtocol.load().sha256,
        "request_count": len(requests),
        "request_hashes": request_hashes,
        "request_bundle_sha256": sha256_text(canonical_json(requests)),
        "request_bytes": [len(canonical_json(request).encode("utf-8")) for request in requests],
        "planned_worst_case_usd": "0.051156",
        "batch_hard_ceiling_usd": str(scope.hard_ceiling_usd),
        "checks": checks,
        "provider_calls": 0,
        "secret_read": False,
        "market_or_effect_read": False,
        "parameter_search_or_backtest": False,
        "paper_web_or_production": False,
        "production_authorization": "none",
        "gate": "GO_PREEXECUTION_ONLY" if all(checks.values()) else "FAIL",
    }
    report["preflight_payload_sha256"] = sha256_text(canonical_json(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        report = preflight()
        write_once(args.output, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"gate": "FAIL", "error_class": "TSV5R3FCanaryPreflightError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"], "request_count": report["request_count"],
        "provider_calls": 0, "secret_read": False,
    }))
    return 0 if report["gate"] == "GO_PREEXECUTION_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
