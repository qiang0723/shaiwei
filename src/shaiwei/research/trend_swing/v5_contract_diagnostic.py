"""Deterministic, redacted diagnosis of the four frozen TS-v5-R2 responses."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_models import (
    ARCHETYPE_CONTRACT,
    COMMON_FEATURES,
    MECHANISM_FEATURES,
    PARAMETER_BOUNDS,
    CancellationRule,
    Feature,
    Mechanism,
    MechanismCandidate,
    ParameterId,
)

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3a_offline_contract_diagnostic_v1.yaml"
SCOPE_SHA256 = "9f82d89ff21c3415182a7fa910dbd972b95e8f4b01a30c52be318b46ea48e4d1"
ATTEMPT_PATH = PROJECT_ROOT / "ledger/ts_v5_r2_llm_attempts.csv"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3a-offline-contract-diagnostic"
REPORT_PATH = OUTPUT_ROOT / "diagnostic.json"

LOCAL_ONLY_CAUSES = ["JSON_SCHEMA_EXPRESSIVENESS_GAP", "PROMPT_CONTRACT_GAP"]
VISIBLE_CAUSE = ["MODEL_INSTRUCTION_NONCOMPLIANCE"]


@dataclass(frozen=True)
class DiagnosticScope:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "DiagnosticScope":
        if path.is_symlink() or sha256_file(path) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R3A diagnostic scope identity differs")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R3A diagnostic scope is invalid") from exc
        if not isinstance(document, dict) or (
            document.get("schema_version") != "ts-v5-r3a-offline-contract-diagnostic-v1"
            or document.get("status") != "RESULT_BLIND_DIAGNOSTIC_FROZEN"
            or document.get("external_api_calls_authorized") != 0
            or document.get("production_authorization") != "none"
            or document.get("diagnostic_method", {}).get("reasoning_content_used") is not False
            or document.get("diagnostic_method", {}).get("repaired_candidate_admission") is not False
        ):
            raise D1ControlError("TS-v5-R3A diagnostic authority differs")
        return cls(document, SCOPE_SHA256)


def _violation(
    rule_id: str, field_path: str, observed: dict[str, Any], *, visible: bool
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "field_path": field_path,
        "observed": observed,
        "transmitted_json_schema": visible,
        "transmitted_prompt_or_candidate_limits": visible,
        "local_custom_validator": not visible,
        "root_causes": VISIBLE_CAUSE if visible else LOCAL_ONLY_CAUSES,
    }


def _parameter_violations(document: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for index, item in enumerate(document.get("parameter_slots", [])):
        if not isinstance(item, dict):
            continue
        try:
            parameter = ParameterId(item["parameter_id"])
            minimum, maximum = Decimal(str(item["minimum"])), Decimal(str(item["maximum"]))
            allowed_minimum, allowed_maximum, allowed_type = PARAMETER_BOUNDS[parameter]
        except (KeyError, ValueError, InvalidOperation):
            continue
        if (
            minimum < allowed_minimum
            or maximum > allowed_maximum
            or item.get("value_type") != allowed_type
        ):
            violations.append(_violation(
                "PARAMETER_SAFE_RANGE",
                f"parameter_slots.{index}",
                {
                    "parameter_id": parameter.value,
                    "submitted_minimum": str(minimum),
                    "submitted_maximum": str(maximum),
                    "allowed_minimum": str(allowed_minimum),
                    "allowed_maximum": str(allowed_maximum),
                    "submitted_type": item.get("value_type"),
                    "allowed_type": allowed_type,
                },
                visible=False,
            ))
    return violations


def diagnose_document(document: dict[str, Any], expected_mechanism: Mechanism) -> dict[str, Any]:
    """Return only structural facts; never return free text from the response."""
    try:
        MechanismCandidate.model_validate(document)
    except ValidationError as exc:
        initial_errors = [
            {"field_path": ".".join(map(str, error["loc"])), "error_type": error["type"]}
            for error in exc.errors(include_input=False, include_url=False)
        ]
    else:
        initial_errors = []
    if document.get("primary_mechanism") != expected_mechanism.value:
        raise D1ControlError("TS-v5-R3A response mechanism identity differs")

    violations: list[dict[str, Any]] = []
    rationale = document.get("economic_rationale_draft")
    if isinstance(rationale, str) and len(rationale) > 800:
        violations.append(_violation(
            "RATIONALE_MAX_LENGTH", "economic_rationale_draft",
            {"submitted_characters": len(rationale), "maximum_characters": 800}, visible=True,
        ))

    features = document.get("required_features", [])
    valid_features: set[Feature] = set()
    invalid_features: list[str] = []
    for value in features if isinstance(features, list) else []:
        try:
            valid_features.add(Feature(value))
        except ValueError:
            invalid_features.append(str(value))
    if invalid_features:
        violations.append(_violation(
            "FEATURE_ENUM_MEMBERSHIP", "required_features",
            {"invalid_values": sorted(invalid_features), "invalid_count": len(invalid_features)},
            visible=True,
        ))

    entry = document.get("entry_design", {})
    cancellation_values = entry.get("cancellation_rules", []) if isinstance(entry, dict) else []
    required_cancellations = {
        CancellationRule.STRUCTURE_LOW_BROKEN.value,
        CancellationRule.MARKET_OR_SECTOR_GATE_LOST.value,
    }
    missing_cancellations = sorted(required_cancellations - set(cancellation_values))
    if missing_cancellations:
        violations.append(_violation(
            "MANDATORY_CANCELLATION_SET", "entry_design.cancellation_rules",
            {"missing_values": missing_cancellations}, visible=False,
        ))

    violations.extend(_parameter_violations(document))
    slots = document.get("parameter_slots", [])
    parameter_ids: set[ParameterId] = set()
    evaluation_count = 1
    for item in slots if isinstance(slots, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            parameter_ids.add(ParameterId(item["parameter_id"]))
        except (KeyError, ValueError):
            pass
        points = item.get("search_points_maximum")
        if isinstance(points, int) and not isinstance(points, bool):
            evaluation_count *= points
    mandatory = ARCHETYPE_CONTRACT[expected_mechanism][2]
    shared = {ParameterId.RECOVERY_CONFIRMATION_DAYS, ParameterId.MAXIMUM_WAIT_DAYS}
    foreign = sorted(item.value for item in parameter_ids - mandatory - shared)
    missing_parameters = sorted(item.value for item in mandatory - parameter_ids)
    if foreign or missing_parameters:
        violations.append(_violation(
            "MECHANISM_PARAMETER_MAPPING", "parameter_slots",
            {"foreign_parameters": foreign, "missing_mandatory_parameters": missing_parameters},
            visible=False,
        ))
    if evaluation_count > 196:
        violations.append(_violation(
            "SEARCH_EVALUATION_PRODUCT", "parameter_slots",
            {"submitted_evaluations": evaluation_count, "maximum_evaluations": 196}, visible=False,
        ))

    required_features = COMMON_FEATURES | MECHANISM_FEATURES[expected_mechanism]
    missing_features = sorted(item.value for item in required_features - valid_features)
    if missing_features:
        violations.append(_violation(
            "MANDATORY_FEATURE_SET", "required_features",
            {"missing_values": missing_features}, visible=False,
        ))

    root_causes = sorted({cause for item in violations for cause in item["root_causes"]})
    return {
        "mechanism": expected_mechanism.value,
        "initial_validator_errors": initial_errors,
        "initial_validator_error_count": len(initial_errors),
        "diagnostic_violations": violations,
        "diagnostic_violation_count": len(violations),
        "root_causes": root_causes,
        "local_validator_defect_detected": not violations and bool(initial_errors),
    }


def _verify_frozen_inputs(scope: DiagnosticScope, project_root: Path) -> list[dict[str, str]]:
    frozen = scope.document["frozen_inputs"]
    checks = {
        "config/ts_v5_evolutionary_research_v1.yaml": frozen["governance_sha256"],
        "config/ts_v5_llm_prompt_v1.yaml": frozen["prompt_sha256"],
        "config/ts_v5_llm_response_contract_v2.yaml": frozen["response_contract_sha256"],
        "config/ts_v5_r2_llm_canary_scope_v1.yaml": frozen["r2_scope_sha256"],
        "config/ts_v5_r2_llm_execution_release_v1.yaml": frozen["r2_release_sha256"],
        "ledger/ts_v5_r2_llm_attempts.csv": frozen["r2_attempt_ledger_sha256"],
        "ledger/ts_v5_r2_llm_transports.csv": frozen["r2_transport_ledger_sha256"],
        "data/research/trend_swing/ts-v5-r2-canary-001/ts_v5_r2_report.json": frozen["r2_report_sha256"],
        "data/research/trend_swing/ts-v5-r2-canary-001/ts_v5_r2_audit.json": frozen["r2_audit_sha256"],
    }
    for relative, expected in checks.items():
        if sha256_file(project_root / relative) != expected:
            raise D1ControlError(f"TS-v5-R3A frozen input differs: {relative}")
    with (project_root / "ledger/ts_v5_r2_llm_attempts.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    raw_hashes = [row["raw_artifact_sha256"] for row in rows]
    if len(rows) != 4 or raw_hashes != frozen["raw_envelope_sha256"]:
        raise D1ControlError("TS-v5-R3A raw response identity differs")
    return rows


def build_report(scope: DiagnosticScope, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    rows = _verify_frozen_inputs(scope, project_root)
    attempts: list[dict[str, Any]] = []
    for row in rows:
        envelope = json.loads((project_root / row["raw_artifact_path"]).read_text(encoding="utf-8"))
        content = envelope.get("content")
        if not isinstance(content, str):
            raise D1ControlError("TS-v5-R3A response content is missing")
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            raise D1ControlError("TS-v5-R3A response content is not JSON") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R3A response content must be an object")
        diagnostic = diagnose_document(document, Mechanism(row["mechanism"]))
        attempts.append({"ordinal": int(row["ordinal"]), **diagnostic})

    cause_counts = {
        cause: sum(cause in item["root_causes"] for item in attempts)
        for cause in (
            "JSON_SCHEMA_EXPRESSIVENESS_GAP",
            "PROMPT_CONTRACT_GAP",
            "MODEL_INSTRUCTION_NONCOMPLIANCE",
            "LOCAL_VALIDATOR_DEFECT",
        )
    }
    local_defect = any(item["local_validator_defect_detected"] for item in attempts)
    if local_defect:
        gate = "STOP_LOCAL_VALIDATOR_DEFECT"
    elif cause_counts["JSON_SCHEMA_EXPRESSIVENESS_GAP"] == 4:
        gate = "GO_R3B_CONTRACT_PROJECTION_RECOVERY_ONLY"
    else:
        gate = "STOP_ROOT_CAUSE_NOT_CLOSED"
    report = {
        "schema_version": "ts-v5-r3a-offline-contract-diagnostic-report-v1",
        "scope_sha256": scope.sha256,
        "input_response_count": len(attempts),
        "attempts": attempts,
        "cause_attempt_counts": cause_counts,
        "all_four_have_non_transmitted_semantic_rule_violations": cause_counts[
            "JSON_SCHEMA_EXPRESSIVENESS_GAP"
        ] == 4,
        "visible_schema_noncompliance_is_secondary": 0
        < cause_counts["MODEL_INSTRUCTION_NONCOMPLIANCE"] < 4,
        "authoritative_root_cause": (
            "INCOMPLETE_LLM_FACING_CONTRACT_PROJECTION"
            if gate == "GO_R3B_CONTRACT_PROJECTION_RECOVERY_ONLY"
            else "NOT_CLOSED"
        ),
        "recommended_recovery": {
            "action": "MECHANISM_SPECIFIC_CONTRACT_PROJECTION_AND_DETERMINISTIC_COMPILER",
            "keep_frozen_validator_unchanged": True,
            "project_exact_parameter_ranges": True,
            "project_mandatory_and_optional_parameter_ids": True,
            "project_maximum_search_product": 196,
            "deterministically_fill_mandatory_cancellations": True,
            "deterministically_fill_required_feature_set": True,
            "llm_decides_only_research_semantics_and_bounded_choices": True,
            "synthetic_and_adversarial_fixture_required_before_new_live_scope": True,
            "new_external_call_requires_new_scope_and_user_approval": True,
        },
        "raw_response_text_persisted": False,
        "reasoning_content_used": False,
        "candidate_repaired_or_admitted": False,
        "market_or_effect_read": False,
        "external_api_calls": 0,
        "parameter_search_or_backtest": False,
        "production_authorization": "none",
        "gate": gate,
    }
    report["diagnostic_payload_sha256"] = sha256_text(canonical_json(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=SCOPE_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        report = build_report(DiagnosticScope.load(args.scope))
        write_once(args.output, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3ADiagnosticError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"], "cause_attempt_counts": report["cause_attempt_counts"],
        "input_response_count": report["input_response_count"], "external_api_calls": 0,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
