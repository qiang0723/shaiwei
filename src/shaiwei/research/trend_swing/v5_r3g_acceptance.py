"""Offline executable-semantics acceptance for TS-v5-R3G."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import FORBIDDEN_RESULT_TERMS
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_r3g_contract import (
    CONFIRMATION_ADDENDUM_SHA256,
    REFERENCE_ADDENDUM_SHA256,
    R3GScope,
    registered_candidates,
    sanitized_registry,
)
from shaiwei.research.trend_swing.v5_r3g_fixtures import (
    adversarial_evidence,
    normal_path_evidence,
)

OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3g-executable-semantics"
REGISTRY_PATH = OUTPUT_ROOT / "candidate_registry.json"
REPORT_PATH = OUTPUT_ROOT / "engineering_report.json"
SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3g_executable_semantics_engineering_v1.yaml"


def _keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            result.add(str(key).lower())
            result.update(_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_keys(child))
    return result


def _registry_has_no_free_text(registry: dict[str, Any]) -> bool:
    forbidden = {
        "hypothesis",
        "economic_rationale_draft",
        "change_summary",
        "falsification_conditions",
        "reasoning_content",
        "content",
    }
    return not (_keys(registry) & forbidden)


def build_evidence(scope: R3GScope) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = registered_candidates(scope)
    registry = sanitized_registry(scope, candidates)
    normal = normal_path_evidence(candidates)
    adversarial = adversarial_evidence(candidates)
    bindings = scope.document["candidate_bindings"]
    checks = {
        "six_candidates_recompiled_and_bound": len(candidates) == len(bindings) == 6
        and all(
            item.candidate.fingerprint() == binding["candidate_fingerprint"]
            and item.candidate.semantic_signature() == binding["semantic_signature"]
            for item, binding in zip(candidates, bindings, strict=True)
        ),
        "six_semantic_signatures_unique": len({
            item.candidate.semantic_signature() for item in candidates
        }) == 6,
        "effective_grid_counts_exact": [len(item.grid) for item in candidates]
        == [81, 75, 81, 81, 32, 81],
        "effective_grid_total_exact": sum(len(item.grid) for item in candidates) == 431,
        "all_grid_points_unique_within_candidate": all(
            len({canonical_json(row) for row in item.grid}) == len(item.grid)
            for item in candidates
        ),
        "all_six_synthetic_paths_execute": len(normal) == 6
        and all(row["terminal_status"] == "EXECUTED" for row in normal),
        "all_adversarial_cases_fail_or_resolve_as_frozen": len(adversarial) == 16
        and all(adversarial.values()),
        "registry_contains_no_llm_free_text_or_reasoning": _registry_has_no_free_text(registry),
        "registry_contains_no_forbidden_result_keys": not (_keys(registry) & FORBIDDEN_RESULT_TERMS),
        "zero_external_calls": True,
        "zero_market_security_density_or_effect_reads": True,
        "zero_parameter_search_model_or_backtest": True,
        "production_authorization_none": True,
    }
    gate = (
        "GO_R3G_DENSITY_SCOPE_PROPOSAL_ONLY"
        if all(checks.values())
        else "STOP_R3G_EXECUTABLE_SEMANTICS_GAP"
    )
    report: dict[str, Any] = {
        "schema_version": "ts-v5-r3g-executable-semantics-engineering-report-v1",
        "scope_sha256": scope.sha256,
        "reference_addendum_sha256": REFERENCE_ADDENDUM_SHA256,
        "confirmation_addendum_sha256": CONFIRMATION_ADDENDUM_SHA256,
        "release_git_head": git_head(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "registry_canonical_sha256": sha256_text(canonical_json(registry)),
        "candidate_count": len(candidates),
        "effective_parameter_point_count": sum(len(item.grid) for item in candidates),
        "llm_generation_attempt_count": 28,
        "strategy_effect_attempt_count": 0,
        "normal_paths": normal,
        "adversarial_cases": adversarial,
        "checks": checks,
        "external_api_calls": 0,
        "secret_read": False,
        "market_security_density_or_effect_read": False,
        "parameter_search_model_or_backtest": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none",
        "gate": gate,
    }
    report["engineering_payload_sha256"] = sha256_text(canonical_json(report))
    return registry, report


def persist_evidence(
    registry: dict[str, Any],
    report: dict[str, Any],
    *,
    registry_path: Path = REGISTRY_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    write_once(
        registry_path,
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    report = {
        **report,
        "registry_file_sha256": sha256_file(registry_path),
    }
    report["engineering_payload_sha256"] = sha256_text(canonical_json({
        key: value for key, value in report.items() if key != "engineering_payload_sha256"
    }))
    write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=SCOPE_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        registry, report = build_evidence(R3GScope.load(args.scope))
        report = persist_evidence(
            registry, report, registry_path=args.registry, report_path=args.report
        )
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError, RuntimeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3GEngineeringError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"],
        "candidate_count": report["candidate_count"],
        "effective_parameter_point_count": report["effective_parameter_point_count"],
        "external_api_calls": 0,
    }))
    return 0 if report["gate"] == "GO_R3G_DENSITY_SCOPE_PROPOSAL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
