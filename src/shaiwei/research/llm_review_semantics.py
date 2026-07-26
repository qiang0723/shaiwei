"""Deterministic, fail-closed semantic contract gate for future D1 reviews."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError


PASS = "PASS_SEMANTIC_CONTRACT"
FAIL = "FAIL_SEMANTIC_CONTRACT"
AMBIGUOUS = "MANUAL_REVIEW_REQUIRED"

DEFAULT_PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_semantic_gate_v1.yaml"
DEFAULT_REVIEW_PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_review_v1.yaml"
DEFAULT_REVIEW_LEDGER_PATH = PROJECT_ROOT / "ledger/llm_factor_reviews.csv"
DEFAULT_CORRECTION_PATH = (
    PROJECT_ROOT / "docs/D1_LLM_FACTOR_REVIEW_SEMANTIC_CORRECTION_20260725.json"
)

_DSL_HEAD = re.compile(
    r"\b(?:Abs|Add|Corr|Cov|Delay|Delta|Div|EMA|Log|Max|Mean|Min|Mul|Rank|Ref|Std|Sub|Sum|TsRank|WMA)\s*\(",
    re.IGNORECASE,
)
_LOOKBACK = re.compile(r"\b(\d{1,4})\s*d\b", re.IGNORECASE)
_DIRECT_CHANGE = re.compile(
    r"\b(?:replace|substitute|swap|rewrite|modify|change|adjust|tune)\w*\b"
    r".{0,100}\b(?:formula|expression|operator|aggregation|estimator|normalization|lookback|window|parameter|direction)\b",
    re.IGNORECASE,
)
_DIRECT_VARIANT = re.compile(
    r"\b(?:try|test|explore|consider|adopt|switch\s+to|move\s+to)\b.{0,100}"
    r"\b(?:variant|alternative|different\s+time\s*scale|jump[- ]based|risk[- ]neutral|"
    r"moving\s+average|mean|median|estimator|normalization|lookback|window|formula|expression)\b",
    re.IGNORECASE,
)
_MODAL_ALTERNATIVE = re.compile(
    r"\b(?:would\s+need|would\s+require|(?:would|should|could|must)\s+"
    r"(?:use|calculate|compute|apply|adopt|replace|change)|"
    r"needs?\s+(?:to\s+)?(?:use|replace|change|adopt)?|requires?\s+(?:using\s+|a\s+|an\s+|the\s+)?|"
    r"recommends?\s+|prefers?\s+|better\s+to\s+|more\s+direct\s+measure\s+would\s+be)\b"
    r".{0,120}\b(?:mean|moving\s+average|median|alternative|different|another|estimator|normalization|"
    r"variant|lookback|window|time\s*scale|aggregation|operator|formula|expression)\b",
    re.IGNORECASE,
)
_IMPERATIVE_ALTERNATIVE = re.compile(
    r"(?:^|[.!?]\s+)(?:use|apply|adopt|replace)\b.{0,100}"
    r"\b(?:mean|moving\s+average|median|alternative|different|another|estimator|normalization|"
    r"variant|lookback|window|time\s*scale|aggregation|operator|formula|expression)\b",
    re.IGNORECASE,
)
_REVERSE_ALTERNATIVE = re.compile(
    r"\b(?:genuinely\s+distinct|different|alternative|another|jump[- ]based|risk[- ]neutral)\b"
    r".{0,120}\b(?:would\s+be|is|are)?\s*(?:required|needed|recommended|preferred)\b",
    re.IGNORECASE,
)
_LOOKBACK_CHANGE = re.compile(
    r"\b(?:different|alternative|shorter|longer|multiple)\s+"
    r"(?:lookbacks?|windows?|time\s*scales?|timescales?|horizons?)\b",
    re.IGNORECASE,
)
_PERFORMANCE_CLAIM = re.compile(
    r"\b(?:observed|achieved|delivered|realized|backtested|outperformed|underperformed)\b"
    r".{0,80}\b(?:rank\s*ic|icir|sharpe|return|alpha|excess|drawdown|performance)\b",
    re.IGNORECASE,
)
_ADMISSION_CLAIM = re.compile(
    r"\b(?:should|can|is\s+ready\s+to|must)\s+"
    r"(?:be\s+)?(?:admit|approve|deploy|promote|accept|productionize)\w*\b",
    re.IGNORECASE,
)
_AMBIGUOUS_RECOMMENDATION = re.compile(
    r"(?:\b(?:mean|moving\s+average|median|estimator|normalization|variant|lookback|window|formula|"
    r"expression|operator|aggregation)\b.{0,80}\b(?:preferable|better|alternative|option|could|may|might)\b|"
    r"\b(?:preferable|better|alternative|option|could|may|might)\b.{0,80}"
    r"\b(?:mean|moving\s+average|median|estimator|normalization|variant|lookback|window|formula|"
    r"expression|operator|aggregation)\b)",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"(?:\bdo\s+not|\bdon't|\bmust\s+not|\bshould\s+not|\bcannot|\bcan't|\bnever|\bwithout|\bno)"
    r"(?:\s+\w+){0,4}\s*$",
    re.IGNORECASE,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _project_path(value: str | Path, *, label: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise D1ControlError(f"{label} must be project-relative")
    resolved = (PROJECT_ROOT / path).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise D1ControlError(f"{label} escapes the project")
    return resolved


@dataclass(frozen=True)
class SemanticGateProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = DEFAULT_PROTOCOL_PATH) -> "SemanticGateProtocol":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise D1ControlError("D1 semantic gate protocol is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("D1 semantic gate protocol must be a YAML object")
        if (
            document.get("schema_version") != "d1-llm-factor-semantic-gate-v1"
            or document.get("protocol_id") != "d1-review-semantic-gate-v1"
            or document.get("status") != "RESULT_BLIND_ENGINEERING_PROTOCOL_FROZEN"
        ):
            raise D1ControlError("D1 semantic gate protocol identity differs")
        authority = document.get("authority_boundary", {})
        if (
            authority.get("prior_authoritative_gate")
            != "STOP_SEMANTIC_CONTRACT_VIOLATION"
            or authority.get("prior_batch_may_be_reopened") is not False
            or authority.get("prior_response_replacement_allowed") is not False
            or authority.get("provider_calls_authorized") is not False
            or authority.get("W1_W6_visible") is not False
            or authority.get("g1_results_visible") is not False
        ):
            raise D1ControlError("D1 semantic gate authority boundary differs")
        policy = document.get("semantic_policy", {})
        verdicts = document.get("verdicts", {})
        if (
            policy.get("ambiguous_text_is_fail_closed") is not True
            or policy.get("narrative_is_never_a_machine_admission_decision") is not True
            or verdicts.get("batch_go_requires_all_pass") is not True
            or verdicts.get("fail_or_ambiguous_stops_batch_before_human_gate") is not True
        ):
            raise D1ControlError("D1 semantic gate fail-closed policy differs")
        return cls(path=path, document=document, sha256=sha256_file(path))


@dataclass(frozen=True)
class SemanticGateResult:
    status: str
    reason_codes: tuple[str, ...]
    inspected_text_sha256: str
    inspected_field_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "inspected_text_sha256": self.inspected_text_sha256,
            "inspected_field_count": self.inspected_field_count,
        }


def _extract_text_fields(document: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    values: list[str] = []
    summary = document.get("summary")
    if not isinstance(summary, str):
        errors.append("INVALID_SUMMARY_SHAPE")
    else:
        values.append(summary)
    findings = document.get("findings")
    if not isinstance(findings, list):
        errors.append("INVALID_FINDINGS_SHAPE")
        return values, errors
    for finding in findings:
        if not isinstance(finding, Mapping):
            errors.append("INVALID_FINDING_SHAPE")
            continue
        for key in ("category", "statement", "falsification_or_resolution"):
            value = finding.get(key)
            if not isinstance(value, str):
                errors.append(f"INVALID_{key.upper()}_SHAPE")
            else:
                values.append(value)
    return values, errors


def _balanced_dsl_expressions(text: str) -> tuple[str, ...]:
    expressions: list[str] = []
    consumed_until = -1
    for match in _DSL_HEAD.finditer(text):
        if match.start() < consumed_until:
            continue
        depth = 0
        end: int | None = None
        for index in range(match.end() - 1, len(text)):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end is None:
            break
        expression = text[match.start() : end]
        if "$" in expression:
            expressions.append(expression)
            consumed_until = end
    return tuple(expressions)


def _normalize_formula(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _is_negated(text: str, start: int) -> bool:
    return _NEGATION.search(text[max(0, start - 55) : start]) is not None


def _action_reasons(text: str) -> set[str]:
    reasons: set[str] = set()
    for pattern, reason in (
        (_DIRECT_CHANGE, "FORMULA_CHANGE_ACTION"),
        (_DIRECT_VARIANT, "NEW_VARIANT_ACTION"),
        (_MODAL_ALTERNATIVE, "ALTERNATIVE_CONSTRUCT_ACTION"),
        (_IMPERATIVE_ALTERNATIVE, "ALTERNATIVE_CONSTRUCT_ACTION"),
        (_REVERSE_ALTERNATIVE, "ALTERNATIVE_CONSTRUCT_ACTION"),
        (_LOOKBACK_CHANGE, "LOOKBACK_CHANGE_ACTION"),
        (_PERFORMANCE_CLAIM, "PERFORMANCE_CLAIM_ACTION"),
        (_ADMISSION_CLAIM, "ADMISSION_CLAIM_ACTION"),
    ):
        for match in pattern.finditer(text):
            if not _is_negated(text, match.start()):
                reasons.add(reason)
    return reasons


def evaluate_semantic_contract(
    document: Mapping[str, Any],
    *,
    allowed_formulas: Sequence[str],
) -> SemanticGateResult:
    """Evaluate one parsed D1 review without returning or persisting its narrative."""

    fail_reasons: set[str] = set()
    ambiguous_reasons: set[str] = set()
    if not allowed_formulas:
        fail_reasons.add("INVALID_ALLOWED_FORMULA_BINDING")
    text_fields, shape_errors = _extract_text_fields(document)
    fail_reasons.update(shape_errors)
    if document.get("formula_change_or_new_candidate_proposed") is not False:
        fail_reasons.add("STRUCTURED_NO_CHANGE_CONTRACT_FAILED")
    if document.get("performance_claim_made") is not False:
        fail_reasons.add("STRUCTURED_PERFORMANCE_CONTRACT_FAILED")

    allowed_normalized = {_normalize_formula(value) for value in allowed_formulas}
    allowed_lookbacks = {
        int(value) for formula in allowed_formulas for value in _LOOKBACK.findall(formula)
    }
    for text in text_fields:
        if any(character.isalpha() and ord(character) > 127 for character in text):
            ambiguous_reasons.add("UNSUPPORTED_REVIEW_LANGUAGE")
        fail_reasons.update(_action_reasons(text))
        expressions = _balanced_dsl_expressions(text)
        if "$" in text and _DSL_HEAD.search(text) and not expressions:
            ambiguous_reasons.add("UNPARSEABLE_DSL_TEXT")
        for expression in expressions:
            if _normalize_formula(expression) not in allowed_normalized:
                fail_reasons.add("DIFFERENT_DSL_EXPRESSION")
        for value in _LOOKBACK.findall(text):
            if int(value) not in allowed_lookbacks:
                fail_reasons.add("DIFFERENT_LOOKBACK_LITERAL")
        for match in _AMBIGUOUS_RECOMMENDATION.finditer(text):
            if not _is_negated(text, match.start()):
                ambiguous_reasons.add("AMBIGUOUS_CHANGE_LANGUAGE")

    inspected_payload = _canonical_json(text_fields)
    if fail_reasons:
        status = FAIL
        reasons = tuple(sorted(fail_reasons | ambiguous_reasons))
    elif ambiguous_reasons:
        status = AMBIGUOUS
        reasons = tuple(sorted(ambiguous_reasons))
    else:
        status = PASS
        reasons = ()
    return SemanticGateResult(
        status=status,
        reason_codes=reasons,
        inspected_text_sha256=_sha256_text(inspected_payload),
        inspected_field_count=len(text_fields),
    )


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise D1ControlError(f"{label} is missing or invalid") from error
    if not isinstance(document, dict):
        raise D1ControlError(f"{label} must be a JSON object")
    return document


def audit_prior_review_batch(
    *,
    semantic_protocol_path: Path = DEFAULT_PROTOCOL_PATH,
    review_protocol_path: Path = DEFAULT_REVIEW_PROTOCOL_PATH,
    review_ledger_path: Path = DEFAULT_REVIEW_LEDGER_PATH,
    correction_path: Path = DEFAULT_CORRECTION_PATH,
) -> dict[str, Any]:
    """Reclassify the frozen review text without changing any prior evidence."""

    protocol = SemanticGateProtocol.load(semantic_protocol_path)
    review_protocol = yaml.safe_load(review_protocol_path.read_text(encoding="utf-8"))
    if not isinstance(review_protocol, dict):
        raise D1ControlError("D1 review protocol must be a YAML object")
    candidates = review_protocol.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise D1ControlError("D1 review protocol candidate binding differs")
    allowed_formulas = tuple(str(candidate["formula"]) for candidate in candidates)

    with review_ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 8 or [int(row["global_ordinal"]) for row in rows] != list(range(1, 9)):
        raise D1ControlError("D1 review ledger is not the frozen complete batch")

    correction = _load_json(correction_path, label="D1 semantic correction")
    known_violations = {
        str(item["review_id"])
        for item in correction.get("semantic_audit", {}).get("violations", [])
    }
    if len(known_violations) != 3:
        raise D1ControlError("D1 correction known-violation set differs")

    results: list[dict[str, Any]] = []
    for row in rows:
        raw_path = _project_path(row["raw_artifact_path"], label="D1 review raw artifact")
        if sha256_file(raw_path) != row["raw_artifact_sha256"]:
            raise D1ControlError("D1 review raw artifact hash differs")
        envelope = _load_json(raw_path, label="D1 review raw artifact")
        if envelope.get("source_response_sha256") != row["response_sha256"]:
            raise D1ControlError("D1 review response identity differs")
        try:
            response = json.loads(str(envelope["content"]))
        except (KeyError, json.JSONDecodeError) as error:
            raise D1ControlError("D1 review response content is invalid") from error
        if not isinstance(response, dict):
            raise D1ControlError("D1 review response must be a JSON object")
        if response.get("candidate_id") != row["candidate_id"] or response.get("role") != row["role"]:
            raise D1ControlError("D1 review response identity differs from its ledger row")
        result = evaluate_semantic_contract(response, allowed_formulas=allowed_formulas)
        results.append(
            {
                "review_id": row["review_id"],
                "candidate_id": row["candidate_id"],
                "global_ordinal": int(row["global_ordinal"]),
                "role": row["role"],
                "response_sha256": row["response_sha256"],
                **result.as_dict(),
            }
        )

    observed_failures = {item["review_id"] for item in results if item["status"] == FAIL}
    observed_ambiguous = {
        item["review_id"] for item in results if item["status"] == AMBIGUOUS
    }
    counts = {status: sum(item["status"] == status for item in results) for status in (PASS, FAIL, AMBIGUOUS)}
    classification_matches_correction = observed_failures == known_violations and not observed_ambiguous
    report = {
        "schema_version": "d1-review-semantic-gate-audit-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "review_protocol_sha256": sha256_file(review_protocol_path),
        "review_ledger_sha256": sha256_file(review_ledger_path),
        "correction_sha256": sha256_file(correction_path),
        "review_count": len(results),
        "counts": counts,
        "classification_matches_correction": classification_matches_correction,
        "known_violation_count": len(known_violations),
        "prior_authoritative_gate": "STOP_SEMANTIC_CONTRACT_VIOLATION",
        "prior_authoritative_gate_unchanged": True,
        "provider_calls": 0,
        "performance_results_read": False,
        "production_authorization": "none",
        "engineering_gate": (
            "GO_SEMANTIC_GATE_ENGINEERING_ONLY"
            if classification_matches_correction
            else "NO_GO_SEMANTIC_GATE_ENGINEERING"
        ),
        "reviews": results,
    }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-prior-batch", action="store_true")
    args = parser.parse_args(argv)
    if not args.verify_prior_batch:
        parser.error("--verify-prior-batch is required")
    report = audit_prior_review_batch()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["engineering_gate"] == "GO_SEMANTIC_GATE_ENGINEERING_ONLY" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
