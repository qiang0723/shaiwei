"""Independent recomputation of the TS-v5-R3E engineering acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_r3e_acceptance import (
    OUTPUT_ROOT,
    REPORT_PATH,
    SCOPE_PATH,
    R3EEngineeringScope,
    build_report,
)

AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def audit_report(scope_path: Path = SCOPE_PATH, report_path: Path = REPORT_PATH) -> dict[str, object]:
    expected = build_report(R3EEngineeringScope.load(scope_path))
    try:
        observed = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3E engineering report is missing or invalid") from exc
    checks = {
        "full_recomputation_equal": observed == expected,
        "engineering_gate_go": observed.get("gate") == "GO_R3F_LIVE_CANARY_SCOPE_PROPOSAL_ONLY",
        "six_synthetic_candidates_compiled": observed.get("synthetic_compiled_candidate_count") == 6,
        "authority_and_schema_checks_pass": all(
            observed.get("checks", {}).get(key) is True
            for key in (
                "all_compiled_candidates_use_bound_independent_mode",
                "all_requests_bind_approved_authority",
                "response_schema_excludes_lineage",
                "response_schema_excludes_search_points",
                "deterministic_search_product_within_196",
            )
        ),
        "all_adversarial_cases_fail_closed": observed.get("checks", {}).get(
            "all_adversarial_cases_fail_closed"
        ) is True,
        "six_legacy_responses_zero_admission": observed.get("legacy_response_count") == 6
        and observed.get("legacy_candidate_admission_count") == 0,
        "legacy_not_repaired": observed.get("checks", {}).get(
            "legacy_documents_not_repaired_or_normalized"
        ) is True,
        "legacy_inputs_byte_immutable": observed.get("checks", {}).get(
            "legacy_inputs_byte_immutable"
        ) is True,
        "no_network_secret_market_effect_or_backtest": observed.get("external_api_calls") == 0
        and observed.get("secret_read") is False
        and observed.get("market_or_effect_read") is False
        and observed.get("parameter_search_or_backtest") is False,
        "strategy_not_evaluated": observed.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": observed.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3E independent audit failed")
    return {
        "schema_version": "ts-v5-r3e-bound-proposal-engineering-audit-v1",
        "scope_sha256": expected["scope_sha256"],
        "engineering_payload_sha256": expected["engineering_payload_sha256"],
        "checks": checks,
        "network_used": False,
        "secret_read": False,
        "verdict": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=SCOPE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--output", type=Path, default=AUDIT_PATH)
    args = parser.parse_args(argv)
    try:
        result = audit_report(args.scope, args.report)
        write_once(args.output, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3EAuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
