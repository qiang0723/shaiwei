"""Independent offline recomputation of the TS-v5-R3D diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_r3d_diagnostic import (
    OUTPUT_ROOT,
    REPORT_PATH,
    SCOPE_PATH,
    R3DDiagnosticScope,
    build_report,
)

AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def audit_report(scope_path: Path = SCOPE_PATH, report_path: Path = REPORT_PATH) -> dict[str, object]:
    expected = build_report(R3DDiagnosticScope.load(scope_path))
    try:
        observed = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3D diagnostic report is missing or invalid") from exc
    checks = {
        "full_recomputation_equal": observed == expected,
        "six_responses_classified": observed.get("input_response_count") == 6,
        "all_six_have_visible_contract_violations": observed.get(
            "visible_contract_violation_attempt_count"
        ) == 6,
        "all_six_expose_authority_binding_gap": observed.get(
            "authority_binding_gap_attempt_count"
        ) == 6,
        "request_did_not_bind_approved_mode": observed.get(
            "request_authority_contract", {}
        ).get("approved_mode_bound_in_request") is False,
        "local_implementation_defect_not_bypassed": observed.get(
            "local_implementation_defect_attempt_count"
        ) == 6 and observed.get("gate") == "STOP_LOCAL_IMPLEMENTATION_DEFECT",
        "secondary_live_decision_not_reached": observed.get(
            "secondary_recoverable_interface_gate"
        ) == "NOT_EVALUATED_DUE_LOCAL_IMPLEMENTATION_DEFECT",
        "no_raw_response_or_reasoning": observed.get("raw_response_text_persisted") is False
        and observed.get("reasoning_content_used") is False,
        "no_candidate_repair": observed.get("r3c_candidate_repaired_normalized_or_admitted")
        is False,
        "no_network_secret_market_effect_or_backtest": observed.get("external_api_calls") == 0
        and observed.get("secret_read") is False
        and observed.get("market_or_effect_read") is False
        and observed.get("parameter_search_or_backtest") is False,
        "strategy_not_evaluated": observed.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": observed.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3D independent audit failed")
    return {
        "schema_version": "ts-v5-r3d-offline-proposal-diagnostic-audit-v1",
        "scope_sha256": expected["scope_sha256"],
        "diagnostic_payload_sha256": expected["diagnostic_payload_sha256"],
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
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3DAuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
