"""Deterministic, redacted diagnosis of the six frozen TS-v5-R3C responses."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_models import FORBIDDEN_TEXT, SAFE_TEXT, Mechanism
from shaiwei.research.trend_swing.v5_proposal_contract import (
    NUMERIC_STRING_PATTERN,
    OPTIONAL_CANCELLATIONS,
    allowed_parameter_ids,
    compile_proposal,
    mechanism_projection,
    proposal_model,
)
from shaiwei.research.trend_swing.v5_r3d_inputs import verify_inputs

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3d_offline_proposal_diagnostic_v1.yaml"
SCOPE_SHA256 = "cbfba18e67ea50469548d46f0d43ccd25d7ba11f3980063022fd809665fb6090"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3d-offline-proposal-diagnostic"
REPORT_PATH = OUTPUT_ROOT / "diagnostic.json"
TEXT_FIELDS = {
    "hypothesis": (20, 500), "economic_rationale_draft": (20, 800),
    "change_summary": (10, 300),
}


@dataclass(frozen=True)
class R3DDiagnosticScope:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "R3DDiagnosticScope":
        if path.is_symlink() or sha256_file(path) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R3D diagnostic scope identity differs")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R3D diagnostic scope is invalid") from exc
        method = document.get("diagnostic_method", {}) if isinstance(document, dict) else {}
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != "ts-v5-r3d-offline-proposal-diagnostic-v1"
            or document.get("status") != "RESULT_BLIND_DIAGNOSTIC_FROZEN"
            or document.get("external_api_calls_authorized") != 0
            or document.get("production_authorization") != "none"
            or method.get("raw_response_count_exact") != 6
            or method.get("reasoning_content_used") is not False
            or method.get("repaired_candidate_admission") is not False
        ):
            raise D1ControlError("TS-v5-R3D diagnostic authority differs")
        return cls(document, SCOPE_SHA256)


def _finding(rule: str, layer: str, path: str, error_type: str) -> dict[str, str]:
    return {"rule_id": rule, "layer": layer, "field_path": path, "error_type": error_type}


def _append(findings: list[dict[str, str]], item: dict[str, str]) -> None:
    if item not in findings:
        findings.append(item)


def _top_level_findings(document: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = {*TEXT_FIELDS, "schema_version", "recovery_confirmation",
                "optional_cancellation_rules", "parameter_slots", "falsification_conditions", "lineage"}
    for key in sorted(required - set(document)):
        _append(findings, _finding("REQUIRED_FIELD_MISSING", "PROPOSAL_JSON_SCHEMA", key, "missing"))
    for key in sorted(set(document) - required):
        _append(findings, _finding("EXTRA_FIELD_FORBIDDEN", "PROPOSAL_JSON_SCHEMA", key, "extra_forbidden"))
    if document.get("schema_version") not in (None, "ts-v5-mechanism-proposal-v2"):
        _append(findings, _finding("SCHEMA_VERSION_LITERAL", "PROPOSAL_JSON_SCHEMA", "schema_version", "literal"))
    return findings


def _text_findings(document: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for key, (minimum, maximum) in TEXT_FIELDS.items():
        value = document.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            _append(findings, _finding("TEXT_TYPE", "PROPOSAL_JSON_SCHEMA", key, "string_type"))
        elif not minimum <= len(value) <= maximum:
            _append(findings, _finding("TEXT_LENGTH", "PROPOSAL_JSON_SCHEMA", key, "string_length"))
        elif not SAFE_TEXT.fullmatch(value) or FORBIDDEN_TEXT.search(value):
            _append(findings, _finding("TEXT_SAFETY", "MECHANISM_PROJECTION", key, "prohibited_text"))
    return findings


def _sequence_findings(document: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    optional = document.get("optional_cancellation_rules")
    if optional is not None:
        if not isinstance(optional, list):
            _append(findings, _finding("OPTIONAL_CANCELLATION_TYPE", "PROPOSAL_JSON_SCHEMA", "optional_cancellation_rules", "list_type"))
        elif len(optional) != len(set(map(str, optional))):
            _append(findings, _finding("OPTIONAL_CANCELLATION_UNIQUE", "MECHANISM_PROJECTION", "optional_cancellation_rules", "duplicate"))
        elif any(value not in {item.value for item in OPTIONAL_CANCELLATIONS} for value in optional):
            _append(findings, _finding("OPTIONAL_CANCELLATION_ENUM", "MECHANISM_PROJECTION", "optional_cancellation_rules", "enum"))
    falsification = document.get("falsification_conditions")
    if falsification is not None:
        if not isinstance(falsification, list):
            _append(findings, _finding("FALSIFICATION_TYPE", "PROPOSAL_JSON_SCHEMA", "falsification_conditions", "list_type"))
        elif not 2 <= len(falsification) <= 5:
            _append(findings, _finding("FALSIFICATION_COUNT", "PROPOSAL_JSON_SCHEMA", "falsification_conditions", "list_length"))
        elif not all(isinstance(value, str) for value in falsification):
            _append(findings, _finding("FALSIFICATION_ITEM_TYPE", "PROPOSAL_JSON_SCHEMA", "falsification_conditions", "string_type"))
        else:
            if len(falsification) != len(set(falsification)):
                _append(findings, _finding("FALSIFICATION_UNIQUE", "MECHANISM_PROJECTION", "falsification_conditions", "duplicate"))
            if any(not SAFE_TEXT.fullmatch(value) or FORBIDDEN_TEXT.search(value) for value in falsification):
                _append(findings, _finding("FALSIFICATION_TEXT_SAFETY", "MECHANISM_PROJECTION", "falsification_conditions", "prohibited_text"))
    return findings


def _parameter_findings(document: dict[str, Any], mechanism: Mechanism) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    slots = document.get("parameter_slots")
    if slots is None:
        return findings
    if not isinstance(slots, list) or not 1 <= len(slots) <= 5:
        return [_finding("PARAMETER_SLOT_COUNT", "PROPOSAL_JSON_SCHEMA", "parameter_slots", "list_length")]
    allowed = {item.value for item in allowed_parameter_ids(mechanism)}
    mandatory = set(mechanism_projection(mechanism)["mandatory_parameter_ids"])
    contracts = {item["parameter_id"]: item for item in mechanism_projection(mechanism)["parameter_contracts"]}
    ids: list[str] = []
    product = 1
    for index, slot in enumerate(slots):
        path = f"parameter_slots.{index}"
        if not isinstance(slot, dict):
            _append(findings, _finding("PARAMETER_SLOT_TYPE", "PROPOSAL_JSON_SCHEMA", path, "object_type"))
            continue
        required = {"parameter_id", "value_type", "minimum", "maximum", "search_points_maximum"}
        if set(slot) != required:
            _append(findings, _finding("PARAMETER_SLOT_FIELDS", "PROPOSAL_JSON_SCHEMA", path, "field_set"))
        parameter_id = slot.get("parameter_id")
        if isinstance(parameter_id, str):
            ids.append(parameter_id)
        if parameter_id not in allowed:
            _append(findings, _finding("PARAMETER_ID_DOMAIN", "MECHANISM_PROJECTION", f"{path}.parameter_id", "enum"))
            continue
        contract = contracts[parameter_id]
        if slot.get("value_type") != contract["value_type"]:
            _append(findings, _finding("PARAMETER_VALUE_TYPE", "MECHANISM_PROJECTION", f"{path}.value_type", "literal"))
        try:
            low, high = Decimal(str(slot.get("minimum"))), Decimal(str(slot.get("maximum")))
            numeric = all(re.fullmatch(NUMERIC_STRING_PATTERN, str(slot.get(key))) for key in ("minimum", "maximum"))
        except (InvalidOperation, TypeError):
            numeric, low, high = False, Decimal(0), Decimal(0)
        if not numeric or low >= high:
            _append(findings, _finding("PARAMETER_NUMERIC_RANGE", "MECHANISM_PROJECTION", path, "decimal_range"))
        elif low < Decimal(contract["minimum_inclusive"]) or high > Decimal(contract["maximum_inclusive"]):
            _append(findings, _finding("PARAMETER_SAFE_RANGE", "MECHANISM_PROJECTION", path, "range"))
        points = slot.get("search_points_maximum")
        if isinstance(points, int) and not isinstance(points, bool) and 2 <= points <= 7:
            product *= points
        else:
            _append(findings, _finding("SEARCH_POINTS_RANGE", "PROPOSAL_JSON_SCHEMA", f"{path}.search_points_maximum", "integer_range"))
    if len(ids) != len(set(ids)):
        _append(findings, _finding("PARAMETER_ID_UNIQUE", "MECHANISM_PROJECTION", "parameter_slots", "duplicate"))
    if not mandatory.issubset(ids):
        _append(findings, _finding("MANDATORY_PARAMETER_SET", "MECHANISM_PROJECTION", "parameter_slots", "set_membership"))
    if product > 196:
        _append(findings, _finding("SEARCH_PRODUCT_LIMIT", "MECHANISM_PROJECTION", "parameter_slots", "product_limit"))
    return findings


def _lineage_findings(document: dict[str, Any]) -> tuple[list[dict[str, str]], bool]:
    findings: list[dict[str, str]] = []
    lineage = document.get("lineage")
    if lineage is None:
        return findings, False
    if not isinstance(lineage, dict):
        return [_finding("LINEAGE_TYPE", "PROPOSAL_JSON_SCHEMA", "lineage", "object_type")], False
    mode, parents = lineage.get("mode"), lineage.get("parent_candidate_fingerprints")
    if set(lineage) != {"mode", "parent_candidate_fingerprints"}:
        _append(findings, _finding("LINEAGE_FIELDS", "PROPOSAL_JSON_SCHEMA", "lineage", "field_set"))
    if mode not in {"INDEPENDENT", "ADVERSARIAL_REVISION"}:
        _append(findings, _finding("LINEAGE_MODE_ENUM", "PROPOSAL_JSON_SCHEMA", "lineage.mode", "literal"))
    if not isinstance(parents, list) or len(parents) > 2:
        _append(findings, _finding("LINEAGE_PARENT_COUNT", "PROPOSAL_JSON_SCHEMA", "lineage.parent_candidate_fingerprints", "list_length"))
    elif any(not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item) for item in parents):
        _append(findings, _finding("LINEAGE_PARENT_HASH", "MECHANISM_PROJECTION", "lineage.parent_candidate_fingerprints", "string_pattern"))
    expected = 0 if mode == "INDEPENDENT" else 1
    if isinstance(parents, list) and mode in {"INDEPENDENT", "ADVERSARIAL_REVISION"} and len(parents) != expected:
        _append(findings, _finding("LINEAGE_MODE_PARENT_COUNT", "MECHANISM_PROJECTION", "lineage", "cross_field"))
    return findings, mode != "INDEPENDENT"


def diagnose_document(document: dict[str, Any], mechanism: Mechanism) -> dict[str, Any]:
    """Classify an R3C document without returning any response text or submitted values."""
    findings = _top_level_findings(document)
    for group in (_text_findings(document), _sequence_findings(document), _parameter_findings(document, mechanism)):
        for item in group:
            _append(findings, item)
    lineage_findings, mode_gap = _lineage_findings(document)
    for item in lineage_findings:
        _append(findings, item)
    try:
        proposal_model(mechanism).model_validate(document)
    except ValidationError as exc:
        validator_errors = [
            {"field_path": ".".join(map(str, item["loc"])), "error_type": item["type"]}
            for item in exc.errors(include_input=False, include_url=False)
        ]
    else:
        validator_errors = []
    compiler_status, compiler_defect = "NOT_EVALUATED_DUE_VISIBLE_VIOLATION", False
    if not findings:
        try:
            compile_proposal(mechanism, document)
        except D1ControlError:
            compiler_status, compiler_defect = "FAIL", True
        else:
            compiler_status = "PASS"
    authority = (
        "FAIL_RESPONSE_LINEAGE_NOT_BOUND_TO_APPROVED_INDEPENDENT_SLOT" if mode_gap else "PASS"
    )
    return {
        "mechanism": mechanism.value,
        "validator_errors": validator_errors,
        "validator_error_count": len(validator_errors),
        "visible_contract_findings": findings,
        "visible_contract_finding_count": len(findings),
        "visible_contract_pass": not findings,
        "compiler_status": compiler_status,
        "authority_binding_status": authority,
        "local_implementation_defect": mode_gap or compiler_defect,
        "raw_response_text_persisted": False,
        "reasoning_content_used": False,
    }


def build_report(scope: R3DDiagnosticScope, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    rows, request_authority = verify_inputs(scope.document, project_root)
    attempts = []
    for row in rows:
        envelope = json.loads((project_root / row["raw_artifact_path"]).read_text(encoding="utf-8"))
        content = envelope.get("content")
        if not isinstance(content, str):
            raise D1ControlError("TS-v5-R3D response content is missing")
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            raise D1ControlError("TS-v5-R3D response content is not JSON") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R3D response content must be an object")
        attempts.append({"ordinal": int(row["ordinal"]), **diagnose_document(document, Mechanism(row["mechanism"]))})
    violation_counts = Counter(
        item["rule_id"] for attempt in attempts for item in attempt["visible_contract_findings"]
    )
    local_defects = sum(attempt["local_implementation_defect"] for attempt in attempts)
    visible_attempts = sum(not attempt["visible_contract_pass"] for attempt in attempts)
    if local_defects:
        gate = "STOP_LOCAL_IMPLEMENTATION_DEFECT"
        secondary = "NOT_EVALUATED_DUE_LOCAL_IMPLEMENTATION_DEFECT"
    else:
        gate = "STOP_NEW_LIVE_BATCH_NOT_JUSTIFIED"
        secondary = "RESULT_BLIND_PRIMARY_RULE_ORDER_NOT_MATERIALIZED"
    report = {
        "schema_version": "ts-v5-r3d-offline-proposal-diagnostic-report-v1",
        "scope_sha256": scope.sha256,
        "input_response_count": len(attempts),
        "attempts": attempts,
        "violation_attempt_counts": dict(sorted(violation_counts.items())),
        "visible_contract_violation_attempt_count": visible_attempts,
        "authority_binding_gap_attempt_count": sum(
            attempt["authority_binding_status"] != "PASS" for attempt in attempts
        ),
        "request_authority_contract": request_authority,
        "local_implementation_defect_attempt_count": local_defects,
        "secondary_recoverable_interface_gate": secondary,
        "authoritative_root_cause": "APPROVED_INDEPENDENT_SLOT_MODE_NOT_BOUND_IN_REQUEST_OR_RUNNER",
        "recommended_recovery": {
            "action": "BIND_ATTEMPT_MODE_AS_DETERMINISTIC_REQUEST_AND_COMPILER_CONSTANT",
            "response_lineage_mode_must_equal_approved_slot_mode": True,
            "runner_evidence_mode_must_derive_from_validated_response_contract": True,
            "keep_candidate_validator_and_research_bounds_unchanged": True,
            "replay_synthetic_and_six_frozen_documents_offline_before_new_scope": True,
            "new_external_call_requires_new_scope_release_and_user_approval": True,
        },
        "r3c_candidate_repaired_normalized_or_admitted": False,
        "raw_response_text_persisted": False,
        "reasoning_content_used": False,
        "external_api_calls": 0,
        "secret_read": False,
        "market_or_effect_read": False,
        "parameter_search_or_backtest": False,
        "candidate_effectiveness": "NOT_EVALUATED",
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
        report = build_report(R3DDiagnosticScope.load(args.scope))
        write_once(args.output, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3DDiagnosticError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"], "input_response_count": report["input_response_count"],
        "local_implementation_defect_attempt_count": report["local_implementation_defect_attempt_count"],
        "external_api_calls": 0,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
