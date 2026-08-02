"""Zero-call fixtures and machine report for compact review contract v2."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from shaiwei.research.compact_review_contract import (
    CATEGORIES,
    DEFAULT_PROTOCOL_PATH,
    ROLES,
    SCHEMA_VERSION,
    SYNTHETIC_CANDIDATE_ID,
    SYNTHETIC_FORMULA,
    CompactReviewProtocol,
    CompactReviewResponse,
    canonical_json,
    validate_response,
)
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import AMBIGUOUS, FAIL, PASS


def maximum_payload() -> dict[str, Any]:
    longest_categories = sorted(CATEGORIES, key=len, reverse=True)[:3]
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": SYNTHETIC_CANDIDATE_ID,
        "role": max(ROLES, key=len),
        "role_verdict": "BLOCKER_FOUND",
        "summary": "S" * 320,
        "findings": [
            {
                "severity": "major",
                "category": category,
                "statement": "A" * 320,
                "falsification_condition": "F" * 240,
            }
            for category in longest_categories
        ],
        "disposition": "REJECT_EXACT_EXPRESSION_AS_IS",
        "formula_change_or_new_candidate_proposed": False,
        "performance_or_admission_claim_made": False,
    }


def _valid_fixture() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": SYNTHETIC_CANDIDATE_ID,
        "role": "construct_and_units",
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": (
            "The exact frozen construct is dimensionless and coherent within this narrow role."
        ),
        "findings": [
            {
                "severity": "minor",
                "category": "scope_limitation",
                "statement": (
                    "The stated mechanism remains conditional on comparable adjusted price histories."
                ),
                "falsification_condition": (
                    "The frozen claim fails if adjusted histories are not comparable at the signal time."
                ),
            }
        ],
        "disposition": "LATER_FROZEN_VALIDATION_ONLY",
        "formula_change_or_new_candidate_proposed": False,
        "performance_or_admission_claim_made": False,
    }


def _schema_fails(protocol: CompactReviewProtocol, document: Mapping[str, Any]) -> bool:
    try:
        validate_response(
            protocol,
            document,
            expected_candidate_id=SYNTHETIC_CANDIDATE_ID,
            expected_role="construct_and_units",
            allowed_formulas=(SYNTHETIC_FORMULA,),
        )
    except (D1ControlError, UnicodeEncodeError, ValidationError, ValueError):
        return True
    return False


def _fixture_checks(protocol: CompactReviewProtocol) -> dict[str, bool]:
    valid = _valid_fixture()
    _, semantic = validate_response(
        protocol,
        valid,
        expected_candidate_id=SYNTHETIC_CANDIDATE_ID,
        expected_role="construct_and_units",
        allowed_formulas=(SYNTHETIC_FORMULA,),
    )
    maximum = maximum_payload()
    CompactReviewResponse.model_validate(maximum)
    maximum_bytes = len(canonical_json(maximum).encode("ascii"))

    too_many = copy.deepcopy(valid)
    too_many["findings"] *= 4
    non_ascii = copy.deepcopy(valid)
    non_ascii["summary"] += " e acute: \u00e9"
    wrong_verdict = copy.deepcopy(valid)
    wrong_verdict["role_verdict"] = "BLOCKER_FOUND"
    wrong_disposition = copy.deepcopy(valid)
    wrong_disposition["disposition"] = "REJECT_EXACT_EXPRESSION_AS_IS"
    repeated_formula = copy.deepcopy(valid)
    repeated_formula["findings"][0]["statement"] = (
        "The repeated Div(Mean($close,5d),Mean($close,20d)) text is unnecessary here."
    )

    semantic_cases: dict[str, tuple[str, str]] = {
        "formula_change": (
            "Replace the formula with another expression before any later test.",
            FAIL,
        ),
        "performance_claim": (
            "The construct backtested with superior return and should be admitted.",
            FAIL,
        ),
        "ambiguous_variant": (
            "An alternative moving average could be a preferable option for later work.",
            AMBIGUOUS,
        ),
    }
    semantic_results: dict[str, bool] = {}
    for label, (statement, expected) in semantic_cases.items():
        changed = copy.deepcopy(valid)
        changed["findings"][0]["statement"] = statement
        _, result = validate_response(
            protocol,
            changed,
            expected_candidate_id=SYNTHETIC_CANDIDATE_ID,
            expected_role="construct_and_units",
            allowed_formulas=(SYNTHETIC_FORMULA,),
        )
        semantic_results[label] = result.status == expected

    return {
        "valid_schema_and_semantic_pass": semantic.status == PASS,
        "maximum_payload_schema_pass": True,
        "maximum_payload_within_4096_bytes": maximum_bytes <= 4096,
        "maximum_payload_below_6000_token_byte_bound": maximum_bytes < 6000,
        "too_many_findings_fail": _schema_fails(protocol, too_many),
        "non_ascii_fails": _schema_fails(protocol, non_ascii),
        "verdict_mismatch_fails": _schema_fails(protocol, wrong_verdict),
        "disposition_mismatch_fails": _schema_fails(protocol, wrong_disposition),
        "formula_text_repetition_fails": _schema_fails(protocol, repeated_formula),
        "formula_change_semantic_fails": semantic_results["formula_change"],
        "performance_claim_semantic_fails": semantic_results["performance_claim"],
        "ambiguous_variant_fail_closed": semantic_results["ambiguous_variant"],
    }


def run_preexecution(path: Path = DEFAULT_PROTOCOL_PATH) -> dict[str, Any]:
    protocol = CompactReviewProtocol.load(path)
    checks = _fixture_checks(protocol)
    maximum_bytes = len(canonical_json(maximum_payload()).encode("ascii"))
    gate = (
        "GO_COMPACT_REVIEW_CONTRACT_V2_ENGINEERING_ONLY"
        if all(checks.values())
        else "NO_GO_COMPACT_REVIEW_CONTRACT_V2_ENGINEERING"
    )
    return {
        "schema_version": "shaiwei-compact-review-contract-v2-preexecution-report",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "semantic_protocol_sha256": protocol.semantic_protocol.sha256,
        "response_schema_sha256": hashlib.sha256(
            canonical_json(CompactReviewResponse.model_json_schema()).encode("ascii")
        ).hexdigest(),
        "maximum_payload_sha256": hashlib.sha256(
            canonical_json(maximum_payload()).encode("ascii")
        ).hexdigest(),
        "maximum_payload_bytes": maximum_bytes,
        "maximum_response_json_bytes": 4096,
        "maximum_output_tokens": 6000,
        "thinking": "disabled",
        "reasoning_effort_field_present": False,
        "illustrative_eight_response_ceiling_usd": 0.08352,
        "fixture_checks": checks,
        "api_key_read": False,
        "provider_calls": 0,
        "real_candidate_or_result_read": False,
        "prior_batches_reopened": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "engineering_gate": gate,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    args = parser.parse_args(argv)
    try:
        report = run_preexecution(args.protocol)
    except (D1ControlError, OSError, TypeError, ValueError, ValidationError):
        print(canonical_json({"engineering_gate": "FAIL", "error_class": "CompactReviewGateError"}))
        return 2
    print(canonical_json(report))
    return 0 if report["engineering_gate"].startswith("GO_") else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
