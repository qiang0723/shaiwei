"""Independent recomputation of the TS-v5-R3A offline diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json
from shaiwei.research.trend_swing.v5_contract_diagnostic import (
    DiagnosticScope,
    OUTPUT_ROOT,
    REPORT_PATH,
    SCOPE_PATH,
    build_report,
)
from shaiwei.research.trend_swing.v5_evidence import write_once

AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def audit_report(
    *, scope_path: Path = SCOPE_PATH, report_path: Path = REPORT_PATH
) -> dict[str, object]:
    expected = build_report(DiagnosticScope.load(scope_path))
    try:
        observed = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3A diagnostic report is missing or invalid") from exc
    checks = {
        "full_recomputation_equal": observed == expected,
        "four_responses_classified": observed.get("input_response_count") == 4,
        "all_four_contract_projection_gap": observed.get(
            "all_four_have_non_transmitted_semantic_rule_violations"
        ) is True,
        "no_local_validator_defect": observed.get("cause_attempt_counts", {}).get(
            "LOCAL_VALIDATOR_DEFECT"
        ) == 0,
        "no_raw_response_or_reasoning": observed.get("raw_response_text_persisted") is False
        and observed.get("reasoning_content_used") is False,
        "no_candidate_repair": observed.get("candidate_repaired_or_admitted") is False,
        "no_network_market_effect_or_backtest": observed.get("external_api_calls") == 0
        and observed.get("market_or_effect_read") is False
        and observed.get("parameter_search_or_backtest") is False,
        "production_authorization_none": observed.get("production_authorization") == "none",
        "recovery_only_gate": observed.get("gate")
        == "GO_R3B_CONTRACT_PROJECTION_RECOVERY_ONLY",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3A independent audit failed")
    return {
        "schema_version": "ts-v5-r3a-offline-contract-diagnostic-audit-v1",
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
        audit = audit_report(scope_path=args.scope, report_path=args.report)
        write_once(args.output, json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3AAuditError"}))
        return 2
    print(canonical_json(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
