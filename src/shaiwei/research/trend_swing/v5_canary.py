"""Zero-call preflight for the TS-v5-R2 four-response contract canary."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import V5Bundle, canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_prompt import plan_attempt
from shaiwei.research.trend_swing.v5_response_contract import (
    CONTRACT_SHA256,
    V5ResponseContract,
    build_request_v2,
)

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r2_llm_canary_scope_v1.yaml"
SCOPE_SHA256 = "e2d7218fc77e918ce3f389263290be6fc5fb15d274ec7affcf75d94e48e1a8ef"
MECHANISMS = (
    "VOLATILITY_ADAPTIVE_PULLBACK",
    "WEEKLY_STRUCTURE_QUANTILE",
    "BREAKOUT_RETEST",
    "MOVING_AVERAGE_RESUMPTION",
)


@dataclass(frozen=True)
class V5CanaryScope:
    """Pinned R2 scope; it describes approval, never grants it."""

    document: dict[str, Any]
    sha256: str
    completed_responses: int
    hard_ceiling_usd: Decimal

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "V5CanaryScope":
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(PROJECT_ROOT.resolve(strict=True))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise D1ControlError("TS-v5-R2 canary scope is missing or outside the project") from exc
        if path.is_symlink() or sha256_file(resolved) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R2 canary scope identity differs")
        try:
            document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R2 canary scope is invalid") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R2 canary scope must be an object")
        attempts = document.get("attempt_contract", {})
        provider = document.get("provider_contract", {})
        identity = document.get("frozen_identity", {})
        cost = document.get("cost_contract", {})
        next_authority = document.get("next_authority_if_user_approves_exact_scope_sha256", {})
        if (
            document.get("schema_version") != "ts-v5-r2-llm-canary-scope-v1"
            or document.get("status") != "AWAITING_EXPLICIT_USER_APPROVAL"
            or document.get("execution_authorized") is not False
            or document.get("user_approval_received") is not False
            or document.get("deepseek_api_called") is not False
            or document.get("production_authorization") != "none"
            or identity.get("response_contract_sha256") != CONTRACT_SHA256
            or provider.get("thinking") != "disabled"
            or provider.get("reasoning_effort") != "omitted"
            or provider.get("maximum_output_tokens_per_response") != 1800
            or attempts.get("completed_response_target_exact") != 4
            or attempts.get("independent_slots") != 4
            or attempts.get("adversarial_revision_slots") != 0
            or attempts.get("mechanism_order") != list(MECHANISMS)
            or attempts.get("replacement_response_authorized") is not False
            or attempts.get("stop_after_four_completed_responses") is not True
            or next_authority.get("market_or_effect_read") is not False
            or next_authority.get("parameter_search_or_backtest") is not False
            or next_authority.get("paper_web_or_production") is not False
        ):
            raise D1ControlError("TS-v5-R2 canary scope broadens or differs")
        worst_case = (
            Decimal(cost["maximum_prompt_tokens_per_slot"])
            * Decimal(cost["input_cache_miss_usd_per_million"])
            + Decimal(cost["maximum_output_tokens_per_slot"])
            * Decimal(cost["output_usd_per_million"])
        ) / Decimal("1000000") * Decimal(4)
        if (
            worst_case != Decimal(cost["planned_worst_case_all_cache_miss_usd"])
            or worst_case != Decimal("0.034104")
            or Decimal(cost["batch_hard_ceiling_usd"]) != Decimal("0.10")
            or worst_case >= Decimal(cost["batch_hard_ceiling_usd"])
        ):
            raise D1ControlError("TS-v5-R2 canary cost contract differs")
        return cls(document, SCOPE_SHA256, 4, Decimal("0.10"))


def preflight() -> dict[str, Any]:
    """Build the exact four-request bundle without secret or provider access."""
    scope = V5CanaryScope.load()
    contract = V5ResponseContract.load()
    bundle = V5Bundle.load()
    requests = [build_request_v2(bundle, plan_attempt(bundle, ordinal), contract=contract) for ordinal in range(1, 5)]
    tasks = [json.loads(request["messages"][1]["content"]) for request in requests]
    checks = {
        "request_count_exact": len(requests) == scope.completed_responses,
        "mechanism_order_exact": [task["primary_mechanism"] for task in tasks] == list(MECHANISMS),
        "independent_only": all(task["mode"] == "INDEPENDENT" for task in tasks),
        "ordinal_domain_exact": [task["ordinal"] for task in tasks] == [1, 2, 3, 4],
        "response_profile_v2": all(
            request.get("thinking") == {"type": "disabled"}
            and "reasoning_effort" not in request
            and request.get("response_format") == {"type": "json_object"}
            and request.get("max_tokens") == 1800
            and request.get("tools") == []
            and request.get("stream") is False
            for request in requests
        ),
        "all_request_hashes_unique": len({sha256_text(canonical_json(item)) for item in requests}) == 4,
        "execution_still_unauthorized": scope.document["execution_authorized"] is False,
    }
    return {
        "schema_version": "ts-v5-r2-canary-preflight-v1",
        "scope_sha256": scope.sha256,
        "response_contract_sha256": contract.sha256,
        "request_count": len(requests),
        "request_hashes": [sha256_text(canonical_json(item)) for item in requests],
        "request_bundle_sha256": sha256_text(canonical_json(requests)),
        "planned_worst_case_usd": "0.034104",
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


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        report = preflight()
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"gate": "FAIL", "error_class": "TSV5R2CanaryPreflightError"}))
        return 2
    print(canonical_json(report))
    return 0 if report["gate"] == "GO_PREEXECUTION_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
