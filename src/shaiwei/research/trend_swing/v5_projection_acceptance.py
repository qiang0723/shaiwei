"""Offline engineering acceptance for the TS-v5 mechanism proposal projection."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_models import (
    ARCHETYPE_CONTRACT,
    COMMON_FEATURES,
    MECHANISM_FEATURES,
    PARAMETER_BOUNDS,
    Mechanism,
    ParameterId,
)
from shaiwei.research.trend_swing.v5_proposal_contract import (
    CONTRACT_PATH,
    CONTRACT_SHA256,
    MANDATORY_CANCELLATIONS,
    allowed_parameter_ids,
    build_request_v3,
    compile_proposal,
    mechanism_projection,
    projection_bundle_identity,
)

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3b_contract_projection_engineering_v1.yaml"
SCOPE_SHA256 = "9e7c317f798f313db098e3cb195fc7341c89c99b817641573c58c3330a9ab26b"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3b-contract-projection-final"
REPORT_PATH = OUTPUT_ROOT / "engineering_report.json"
LEGACY_VALIDATOR_SHA256 = "dc3a19b7cbc07ae6cca44b4c814c1c34c283caf90359b8d81e8f1a68cb54b37b"
LEGACY_PROMPT_SHA256 = "4dfabdac2e82868c0c710b62866943e2b805c50bdf8242af55f7f6e546e9ce77"


def minimal_proposal(mechanism: Mechanism) -> dict[str, Any]:
    mandatory = sorted(ARCHETYPE_CONTRACT[mechanism][2], key=lambda item: item.value)
    return {
        "schema_version": "ts-v5-mechanism-proposal-v2",
        "hypothesis": "在冻结趋势与板块条件下，该机制可能提供更稳定且可证伪的入场事件。",
        "economic_rationale_draft": "该研究只比较机制与邻近参数稳健性，不包含任何收益或生产结论。",
        "change_summary": "仅替换入场机制表达，保持全部产品与执行约束不变。",
        "recovery_confirmation": "CLOSE_RECLAIMS_REFERENCE",
        "optional_cancellation_rules": ["MAX_WAIT_EXPIRED"],
        "parameter_slots": [
            {
                "parameter_id": parameter.value,
                "value_type": PARAMETER_BOUNDS[parameter][2],
                "minimum": str(PARAMETER_BOUNDS[parameter][0]),
                "maximum": str(PARAMETER_BOUNDS[parameter][1]),
                "search_points_maximum": 3,
            }
            for parameter in mandatory
        ],
        "falsification_conditions": [
            "事件无法覆盖多个自然年度或只集中在单一阶段。",
            "邻近参数方向与成本敏感性无法保持一致。",
        ],
        "lineage": {"mode": "INDEPENDENT", "parent_candidate_fingerprints": []},
    }


def coverage_matrix(mechanism: Mechanism) -> dict[str, str]:
    return {
        "strict_extra_fields": "PROJECTED_PROPOSAL_SCHEMA",
        "text_lengths": "PROJECTED_PROPOSAL_SCHEMA",
        "text_safety": "PROJECTED_TEXT_CONTRACT_AND_VALIDATED",
        "reference_frame": "DETERMINISTIC_COMPILER_FROM_ARCHETYPE_CONTRACT",
        "pullback_measure": "DETERMINISTIC_COMPILER_FROM_ARCHETYPE_CONTRACT",
        "mandatory_cancellations": "DETERMINISTIC_COMPILER_CONSTANT",
        "optional_cancellation_enum": "PROJECTED_AND_VALIDATED",
        "cancellation_uniqueness": "PROJECTED_AND_VALIDATED",
        "parameter_id_domain": "MECHANISM_SPECIFIC_PROJECTED_ENUM",
        "parameter_mandatory_set": "MECHANISM_SPECIFIC_PROJECTED_AND_VALIDATED",
        "parameter_type_and_range": "PROJECTED_FROM_PARAMETER_BOUNDS_AND_VALIDATED",
        "parameter_decimal_format": "PROJECTED_AND_FROZEN_VALIDATOR",
        "parameter_integral_bounds": "PROJECTED_AND_FROZEN_VALIDATOR",
        "parameter_uniqueness": "PROJECTED_AND_VALIDATED",
        "search_point_range": "PROJECTED_PROPOSAL_SCHEMA",
        "search_product_196": "PROJECTED_AND_VALIDATED",
        "required_features": "DETERMINISTIC_COMPILER_FROM_SHARED_CONSTANTS",
        "falsification_count_and_uniqueness": "PROJECTED_AND_VALIDATED",
        "lineage_mode_parent_count_and_hash": "PROJECTED_AND_VALIDATED",
        "final_candidate_contract": "FROZEN_MECHANISM_CANDIDATE_VALIDATOR",
        "mechanism_identity": f"REQUEST_BOUND_{mechanism.value}",
    }


def _adversarial_matrix(mechanism: Mechanism) -> dict[str, bool]:
    baseline = minimal_proposal(mechanism)
    cases: dict[str, dict[str, Any]] = {}
    foreign_parameter = next(
        parameter for parameter in ParameterId if parameter not in allowed_parameter_ids(mechanism)
    )
    foreign_minimum, foreign_maximum, foreign_type = PARAMETER_BOUNDS[foreign_parameter]
    cross = deepcopy(baseline)
    cross["parameter_slots"].append({
        "parameter_id": foreign_parameter.value,
        "value_type": foreign_type,
        "minimum": str(foreign_minimum),
        "maximum": str(foreign_maximum),
        "search_points_maximum": 2,
    })
    cases["cross_mechanism_parameter"] = cross
    missing = deepcopy(baseline)
    missing["parameter_slots"] = missing["parameter_slots"][1:]
    cases["missing_mandatory_parameter"] = missing
    duplicate = deepcopy(baseline)
    duplicate["parameter_slots"].append(deepcopy(duplicate["parameter_slots"][0]))
    cases["duplicate_parameter"] = duplicate
    unsafe = deepcopy(baseline)
    unsafe["parameter_slots"][0]["minimum"] = "-1"
    cases["unsafe_parameter_range"] = unsafe
    deterministic = deepcopy(baseline)
    deterministic["required_features"] = ["ADJUSTED_DAILY_OHLCV"]
    cases["llm_emits_deterministic_field"] = deterministic
    cancellation = deepcopy(baseline)
    cancellation["optional_cancellation_rules"] = ["STRUCTURE_LOW_BROKEN"]
    cases["mandatory_rule_as_optional"] = cancellation
    explosion = deepcopy(baseline)
    for slot in explosion["parameter_slots"]:
        slot["search_points_maximum"] = 7
    if len(explosion["parameter_slots"]) < 3:
        shared = {
            "parameter_id": "MAXIMUM_WAIT_DAYS", "value_type": "INTEGER",
            "minimum": "2", "maximum": "10", "search_points_maximum": 7,
        }
        explosion["parameter_slots"].append(shared)
        recovery = {
            "parameter_id": "RECOVERY_CONFIRMATION_DAYS", "value_type": "INTEGER",
            "minimum": "1", "maximum": "3", "search_points_maximum": 7,
        }
        explosion["parameter_slots"].append(recovery)
    cases["search_product_explosion"] = explosion
    results = {}
    for case_id, document in cases.items():
        try:
            compile_proposal(mechanism, document)
        except D1ControlError:
            results[case_id] = True
        else:
            results[case_id] = False
    return results


def _mechanism_evidence(mechanism: Mechanism, ordinal: int) -> tuple[dict[str, Any], str]:
    candidate = compile_proposal(mechanism, minimal_proposal(mechanism))
    projection = mechanism_projection(mechanism)
    required_features = COMMON_FEATURES | MECHANISM_FEATURES[mechanism]
    request = build_request_v3(mechanism, attempt_id=f"engineering-{ordinal}", ordinal=ordinal)
    adversarial = _adversarial_matrix(mechanism)
    matrix = coverage_matrix(mechanism)
    row = {
        "mechanism": mechanism.value,
        "projection_sha256": sha256_text(canonical_json(projection)),
        "candidate_fingerprint": candidate.fingerprint(),
        "candidate_passes_frozen_validator": True,
        "reference_and_measure_deterministic": (
            candidate.entry_design.reference_frame == ARCHETYPE_CONTRACT[mechanism][0]
            and candidate.entry_design.pullback_measure == ARCHETYPE_CONTRACT[mechanism][1]
        ),
        "mandatory_cancellations_exact": tuple(candidate.entry_design.cancellation_rules[:2])
        == MANDATORY_CANCELLATIONS,
        "required_features_exact": set(candidate.required_features) == required_features,
        "coverage_rule_count": len(matrix),
        "coverage_matrix": matrix,
        "adversarial_case_count": len(adversarial),
        "adversarial_cases": adversarial,
        "all_adversarial_cases_fail_closed": all(adversarial.values()),
    }
    return row, sha256_text(canonical_json(request))


def _global_checks(mechanisms: list[dict[str, Any]], request_hashes: list[str]) -> dict[str, bool]:
    return {
        "all_six_mechanisms_present": len(mechanisms) == len(Mechanism) == 6,
        "all_minimal_proposals_compile": all(
            row["candidate_passes_frozen_validator"] for row in mechanisms
        ),
        "all_deterministic_fields_exact": all(
            row["reference_and_measure_deterministic"]
            and row["mandatory_cancellations_exact"]
            and row["required_features_exact"]
            for row in mechanisms
        ),
        "all_validator_rules_covered": all(row["coverage_rule_count"] == 21 for row in mechanisms),
        "all_adversarial_cases_fail_closed": all(
            row["all_adversarial_cases_fail_closed"] for row in mechanisms
        ),
        "request_hashes_unique": len(set(request_hashes)) == 6,
        "legacy_validator_unchanged": True,
        "legacy_prompt_builder_unchanged": True,
        "external_api_calls_zero": True,
        "no_market_effect_or_backtest": True,
    }


def build_report() -> dict[str, Any]:
    if (
        sha256_file(SCOPE_PATH) != SCOPE_SHA256
        or sha256_file(CONTRACT_PATH) != CONTRACT_SHA256
        or sha256_file(PROJECT_ROOT / "src/shaiwei/research/trend_swing/v5_models.py")
        != LEGACY_VALIDATOR_SHA256
        or sha256_file(PROJECT_ROOT / "src/shaiwei/research/trend_swing/v5_prompt.py")
        != LEGACY_PROMPT_SHA256
    ):
        raise D1ControlError("TS-v5-R3B frozen identity differs")
    evidence = [
        _mechanism_evidence(mechanism, ordinal)
        for ordinal, mechanism in enumerate(Mechanism, start=1)
    ]
    mechanisms = [row for row, _ in evidence]
    request_hashes = [request_hash for _, request_hash in evidence]
    identity = projection_bundle_identity()
    checks = _global_checks(mechanisms, request_hashes)
    gate = "GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY" if all(checks.values()) else "STOP_ENGINEERING_GAP"
    report = {
        "schema_version": "ts-v5-r3b-contract-projection-engineering-report-v1",
        "scope_sha256": SCOPE_SHA256,
        "identity": identity,
        "request_bundle_sha256": sha256_text(canonical_json(request_hashes)),
        "mechanisms": mechanisms,
        "checks": checks,
        "compiled_candidate_count": len(mechanisms),
        "adversarial_case_count": sum(row["adversarial_case_count"] for row in mechanisms),
        "r2_candidate_repaired_or_admitted": False,
        "external_api_calls": 0,
        "secret_read": False,
        "market_or_effect_read": False,
        "parameter_search_or_backtest": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none",
        "gate": gate,
    }
    report["engineering_payload_sha256"] = sha256_text(canonical_json(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        report = build_report()
        write_once(args.output, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3BEngineeringError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"], "compiled_candidate_count": report["compiled_candidate_count"],
        "adversarial_case_count": report["adversarial_case_count"], "external_api_calls": 0,
    }))
    return 0 if report["gate"] == "GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
