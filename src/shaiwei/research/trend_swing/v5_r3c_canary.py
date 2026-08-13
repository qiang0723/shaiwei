"""Zero-call preflight and response classification for the TS-v5-R3C canary."""

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
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import usage_and_cost, write_once
from shaiwei.research.trend_swing.v5_models import Mechanism, MechanismCandidate
from shaiwei.research.trend_swing.v5_proposal_contract import (
    CONTRACT_SHA256,
    ProposalContract,
    build_request_v3,
    compile_proposal,
    projection_bundle_identity,
)
from shaiwei.research.trend_swing.v5_response_contract import (
    CONTRACT_SHA256 as TERMINAL_CONTRACT_SHA256,
    V5ResponseContract,
)
from shaiwei.research.trend_swing.v5_transport import V5TransportProtocol

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3c_llm_canary_scope_v1.yaml"
SCOPE_SHA256 = "234621cf0280fceca82a8e5f82d6966b27979fde761d68b2508346a2ebd953ae"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3c-preflight-001"
REPORT_PATH = OUTPUT_ROOT / "preflight_report.json"
MECHANISMS = tuple(Mechanism)
WORST_CASE_SLOT_USD = (
    Decimal(16_000) * Decimal("0.435") + Decimal(1_800) * Decimal("0.87")
) / Decimal(1_000_000)


@dataclass(frozen=True)
class R3CCanaryScope:
    document: dict[str, Any]
    sha256: str
    completed_responses: int
    hard_ceiling_usd: Decimal

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "R3CCanaryScope":
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(PROJECT_ROOT.resolve(strict=True))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise D1ControlError("TS-v5-R3C scope is missing or outside the project") from exc
        if path.is_symlink() or sha256_file(resolved) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R3C scope identity differs")
        try:
            document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R3C scope is invalid") from exc
        cls._validate(document)
        return cls(document, SCOPE_SHA256, 6, Decimal("0.15"))

    @staticmethod
    def _validate(document: Any) -> None:
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R3C scope must be an object")
        attempts = document.get("attempt_contract", {})
        provider = document.get("provider_contract", {})
        identity = document.get("frozen_identity", {})
        authority = document.get("next_authority_if_user_approves_exact_scope_sha256", {})
        expected_order = [mechanism.value for mechanism in MECHANISMS]
        if (
            document.get("schema_version") != "ts-v5-r3c-llm-canary-scope-v1"
            or document.get("status") != "AWAITING_EXPLICIT_USER_APPROVAL"
            or document.get("execution_authorized") is not False
            or document.get("user_approval_received") is not False
            or document.get("deepseek_api_called") is not False
            or document.get("production_authorization") != "none"
            or identity.get("proposal_contract_sha256") != CONTRACT_SHA256
            or identity.get("response_terminal_contract_sha256") != TERMINAL_CONTRACT_SHA256
            or provider.get("thinking") != "disabled"
            or provider.get("reasoning_effort") != "omitted"
            or provider.get("maximum_output_tokens_per_response") != 1800
            or attempts.get("completed_response_target_exact") != 6
            or attempts.get("mechanism_order") != expected_order
            or attempts.get("replacement_response_authorized") is not False
            or attempts.get("stop_after_six_completed_responses") is not True
            or authority.get("market_or_effect_read") is not False
            or authority.get("parameter_search_or_backtest") is not False
            or authority.get("paper_web_or_production") is not False
        ):
            raise D1ControlError("TS-v5-R3C scope broadens or differs")
        cost = document.get("cost_contract", {})
        planned = WORST_CASE_SLOT_USD * Decimal(6)
        if (
            planned != Decimal(str(cost.get("planned_worst_case_all_cache_miss_usd")))
            or planned != Decimal("0.051156")
            or Decimal(str(cost.get("batch_hard_ceiling_usd"))) != Decimal("0.15")
            or planned >= Decimal(str(cost.get("batch_hard_ceiling_usd")))
        ):
            raise D1ControlError("TS-v5-R3C cost contract differs")


def attempt_id(mechanism: Mechanism, ordinal: int) -> str:
    slug = mechanism.value.lower().replace("_", "-")
    return f"ts-v5-r3c-i{ordinal:02d}-{slug}"


def request_bundle() -> list[dict[str, Any]]:
    contract = ProposalContract.load()
    return [
        build_request_v3(
            mechanism, attempt_id=attempt_id(mechanism, ordinal), ordinal=ordinal,
            contract=contract,
        )
        for ordinal, mechanism in enumerate(MECHANISMS, start=1)
    ]


def classify_proposal_response(
    mechanism: Mechanism,
    response: ProviderResponse,
    *,
    prior_semantic_signatures: set[str] | None = None,
) -> dict[str, Any]:
    """Apply terminal, proposal, compiler and duplicate gates without persistence."""
    try:
        usage, cost = usage_and_cost(V5TransportProtocol.load(), response)
    except D1ControlError:
        usage = {
            "prompt_tokens": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
            "completion_tokens": 0,
        }
        cost = float(WORST_CASE_SLOT_USD)
        failure = "PROVIDER_USAGE_INVALID_WORST_CASE_RESERVED"
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
            candidate = compile_proposal(mechanism, document)
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
            failure = "PROPOSAL_SCHEMA_OR_COMPILER_INVALID"
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
        return "GO_CONTRACT_PROJECTION_CANARY_ONLY"
    if valid_unique_count >= 4:
        return "STOP_PARTIAL_CONTRACT_COMPLIANCE"
    if valid_unique_count >= 1:
        return "STOP_WEAK_CONTRACT_COMPLIANCE"
    return "STOP_NO_VALID_CANDIDATES"


def _request_checks(requests: list[dict[str, Any]], scope: R3CCanaryScope) -> dict[str, bool]:
    tasks = [json.loads(request["messages"][1]["content"]) for request in requests]
    request_hashes = [sha256_text(canonical_json(request)) for request in requests]
    mechanisms = [task["mechanism_projection"]["primary_mechanism"] for task in tasks]
    return {
        "request_count_exact": len(requests) == scope.completed_responses,
        "mechanism_order_exact": mechanisms == [item.value for item in MECHANISMS],
        "attempt_identity_unique": len({task["attempt_id"] for task in tasks}) == 6,
        "ordinal_domain_exact": [task["ordinal"] for task in tasks] == list(range(1, 7)),
        "schema_projection_mechanism_bound": all(
            task["proposal_schema"]["x-ts-mechanism-projection"]
            == task["mechanism_projection"] for task in tasks
        ),
        "response_profile_exact": all(
            request.get("thinking") == {"type": "disabled"}
            and "reasoning_effort" not in request
            and request.get("response_format") == {"type": "json_object"}
            and request.get("max_tokens") == 1800
            and request.get("tools") == []
            and request.get("stream") is False for request in requests
        ),
        "request_hashes_unique": len(set(request_hashes)) == 6,
        "each_request_below_48kb": all(
            len(canonical_json(request).encode("utf-8")) <= 48_000 for request in requests
        ),
        "all_terminal_gates_enumerated": all(
            batch_gate(6, count) != "" for count in range(7)
        ),
        "execution_still_unauthorized": scope.document["execution_authorized"] is False,
    }


def preflight() -> dict[str, Any]:
    scope = R3CCanaryScope.load()
    requests = request_bundle()
    request_hashes = [sha256_text(canonical_json(request)) for request in requests]
    checks = _request_checks(requests, scope)
    report = {
        "schema_version": "ts-v5-r3c-canary-preflight-v1",
        "scope_sha256": scope.sha256,
        "projection_identity": projection_bundle_identity(),
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
        print(canonical_json({"gate": "FAIL", "error_class": "TSV5R3CCanaryPreflightError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"], "request_count": report["request_count"],
        "provider_calls": 0, "secret_read": False,
    }))
    return 0 if report["gate"] == "GO_PREEXECUTION_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
