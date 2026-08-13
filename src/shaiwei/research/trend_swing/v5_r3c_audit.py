"""Independent zero-call audit of the TS-v5-R3C preflight report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_r3c_canary import OUTPUT_ROOT, REPORT_PATH, preflight

AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def audit_report(report_path: Path = REPORT_PATH) -> dict[str, object]:
    expected = preflight()
    try:
        observed = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3C preflight report is missing or invalid") from exc
    checks = {
        "full_recomputation_equal": observed == expected,
        "six_requests_present": observed.get("request_count") == 6,
        "all_preflight_checks_pass": all(observed.get("checks", {}).values()),
        "request_hashes_unique": len(set(observed.get("request_hashes", []))) == 6,
        "request_bundle_bound": len(str(observed.get("request_bundle_sha256", ""))) == 64,
        "zero_provider_calls": observed.get("provider_calls") == 0,
        "no_secret_market_effect_or_backtest": observed.get("secret_read") is False
        and observed.get("market_or_effect_read") is False
        and observed.get("parameter_search_or_backtest") is False,
        "no_paper_web_or_production": observed.get("paper_web_or_production") is False
        and observed.get("production_authorization") == "none",
        "preexecution_only": observed.get("gate") == "GO_PREEXECUTION_ONLY",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3C independent preflight audit failed")
    return {
        "schema_version": "ts-v5-r3c-canary-preflight-audit-v1",
        "scope_sha256": expected["scope_sha256"],
        "preflight_payload_sha256": expected["preflight_payload_sha256"],
        "request_bundle_sha256": expected["request_bundle_sha256"],
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
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3CPreflightAuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
