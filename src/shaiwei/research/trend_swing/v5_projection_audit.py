"""Independent offline audit of the TS-v5-R3B projection engineering report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_projection_acceptance import (
    OUTPUT_ROOT,
    REPORT_PATH,
    build_report,
)

AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def audit_report(report_path: Path = REPORT_PATH) -> dict[str, object]:
    expected = build_report()
    try:
        observed = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3B engineering report is missing or invalid") from exc
    checks = {
        "full_recomputation_equal": observed == expected,
        "six_candidates_compile": observed.get("compiled_candidate_count") == 6,
        "forty_two_adversarial_cases_fail_closed": observed.get("adversarial_case_count") == 42,
        "all_engineering_checks_pass": all(observed.get("checks", {}).values()),
        "legacy_contracts_unchanged": observed.get("checks", {}).get("legacy_validator_unchanged")
        is True and observed.get("checks", {}).get("legacy_prompt_builder_unchanged") is True,
        "no_r2_candidate_repair": observed.get("r2_candidate_repaired_or_admitted") is False,
        "no_network_secret_market_effect_or_backtest": observed.get("external_api_calls") == 0
        and observed.get("secret_read") is False
        and observed.get("market_or_effect_read") is False
        and observed.get("parameter_search_or_backtest") is False,
        "strategy_not_evaluated": observed.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": observed.get("production_authorization") == "none",
        "scope_proposal_only_gate": observed.get("gate")
        == "GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3B independent audit failed")
    return {
        "schema_version": "ts-v5-r3b-contract-projection-audit-v1",
        "scope_sha256": expected["scope_sha256"],
        "engineering_payload_sha256": expected["engineering_payload_sha256"],
        "checks": checks,
        "network_used": False,
        "secret_read": False,
        "verdict": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--output", type=Path, default=AUDIT_PATH)
    args = parser.parse_args(argv)
    try:
        result = audit_report(args.report)
        write_once(args.output, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3BAuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
