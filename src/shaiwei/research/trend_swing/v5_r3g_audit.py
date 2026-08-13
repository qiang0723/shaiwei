"""Independent offline audit for TS-v5-R3G engineering evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_r3g_acceptance import (
    OUTPUT_ROOT,
    REGISTRY_PATH,
    REPORT_PATH,
    SCOPE_PATH,
    build_evidence,
    persist_evidence,
)
from shaiwei.research.trend_swing.v5_r3g_contract import R3GScope

AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3G audit evidence is invalid") from exc
    if not isinstance(value, dict):
        raise D1ControlError("TS-v5-R3G audit evidence is not an object")
    return value


def audit_report(
    *,
    scope_path: Path = SCOPE_PATH,
    registry_path: Path = REGISTRY_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, object]:
    expected_registry, expected_report = build_evidence(R3GScope.load(scope_path))
    expected_report = persist_evidence(
        expected_registry,
        expected_report,
        registry_path=registry_path,
        report_path=report_path,
    )
    registry, report = _load(registry_path), _load(report_path)
    checks = {
        "registry_full_recomputation_equal": registry == expected_registry,
        "report_full_recomputation_equal": report == expected_report,
        "registry_file_hash_bound": report.get("registry_file_sha256") == sha256_file(registry_path),
        "registry_canonical_hash_bound": report.get("registry_canonical_sha256")
        == sha256_text(canonical_json(registry)),
        "six_candidates_bound": report.get("candidate_count") == 6,
        "effective_grid_total_exact": report.get("effective_parameter_point_count") == 431,
        "all_engineering_checks_pass": all(report.get("checks", {}).values()),
        "generation_and_effect_attempts_separate": report.get("llm_generation_attempt_count") == 28
        and report.get("strategy_effect_attempt_count") == 0,
        "no_network_secret_market_or_effect": report.get("external_api_calls") == 0
        and report.get("secret_read") is False
        and report.get("market_security_density_or_effect_read") is False,
        "no_parameter_search_model_or_backtest": report.get(
            "parameter_search_model_or_backtest"
        ) is False,
        "candidate_not_evaluated": report.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": report.get("production_authorization") == "none",
        "gate_is_density_scope_proposal_only": report.get("gate")
        == "GO_R3G_DENSITY_SCOPE_PROPOSAL_ONLY",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3G independent audit failed")
    return {
        "schema_version": "ts-v5-r3g-executable-semantics-independent-audit-v1",
        "scope_sha256": expected_report["scope_sha256"],
        "registry_file_sha256": sha256_file(registry_path),
        "engineering_report_sha256": sha256_file(report_path),
        "engineering_payload_sha256": expected_report["engineering_payload_sha256"],
        "checks": checks,
        "network_used": False,
        "secret_read": False,
        "verdict": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=SCOPE_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--output", type=Path, default=AUDIT_PATH)
    args = parser.parse_args(argv)
    try:
        audit = audit_report(
            scope_path=args.scope, registry_path=args.registry, report_path=args.report
        )
        write_once(args.output, json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError, RuntimeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3GAuditError"}))
        return 2
    print(canonical_json(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
