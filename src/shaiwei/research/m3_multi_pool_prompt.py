"""Strict prompt and bounded-feedback contract for the M3-1 research family."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import CandidateProposal, D1ControlError


PROMPT_SCHEMA = "m3-multi-pool-factor-prompt-v1"
PROMPT_ID = "m3-star-three-pool-price-volume-prompt-v1"
TOPICS = (
    "trend_momentum",
    "reversal_mean_reversion",
    "volatility_range",
    "liquidity_volume",
)
_TEXT_FIELDS = {
    "attempt_id",
    "topic",
    "parse_status",
    "sandbox_status",
    "semantic_status",
    "canonical_expression",
    "failure_class",
}
_FLOAT_FIELDS = {
    "cross_pool_min_coverage",
    "cross_pool_worst_directed_rank_ic",
    "cross_pool_median_directed_rank_ic",
}
_INTEGER_FIELDS = {
    "global_ordinal",
    "expression_tokens",
    "ast_nodes",
    "max_lookback_days",
}


@dataclass(frozen=True)
class M3PromptBundle:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str) -> "M3PromptBundle":
        if not path.is_file() or sha256_file(path) != expected_sha256:
            raise D1ControlError("M3-1 prompt bundle is missing or differs from its freeze")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise D1ControlError("M3-1 prompt bundle must be a YAML object")
        if (
            document.get("schema_version") != PROMPT_SCHEMA
            or document.get("prompt_id") != PROMPT_ID
            or document.get("language") != "zh-CN"
        ):
            raise D1ControlError("M3-1 prompt named identity differs")
        system_prompt = document.get("system_prompt")
        if not isinstance(system_prompt, str) or len(system_prompt.strip()) < 300:
            raise D1ControlError("M3-1 system prompt is missing or too short")
        if tuple(document.get("topic_order", ())) != TOPICS:
            raise D1ControlError("M3-1 prompt topic order differs")
        templates = document.get("topic_templates")
        if not isinstance(templates, dict) or tuple(templates) != TOPICS:
            raise D1ControlError("M3-1 prompt templates differ from the frozen topics")
        for topic, template in templates.items():
            if (
                not isinstance(template, dict)
                or not isinstance(template.get("objective"), str)
                or not template.get("allowed_questions")
                or not template.get("guardrails")
            ):
                raise D1ControlError(f"M3-1 prompt topic is incomplete: {topic}")
        try:
            example = CandidateProposal.model_validate(
                document["candidate_output_contract"]["example"]
            )
        except (KeyError, TypeError, ValidationError) as error:
            raise D1ControlError("M3-1 prompt candidate example is invalid") from error
        if example.topic not in TOPICS:
            raise D1ControlError("M3-1 prompt example uses an unscheduled topic")
        cls._validate_feedback_contract(document.get("feedback_contract"))
        return cls(path=path, document=document, sha256=expected_sha256)

    @staticmethod
    def _validate_feedback_contract(value: object) -> None:
        if not isinstance(value, dict):
            raise D1ControlError("M3-1 feedback contract must be an object")
        allowed = value.get("allowed_fields")
        forbidden = value.get("forbidden_fields")
        if not isinstance(allowed, list) or len(allowed) != len(set(allowed)):
            raise D1ControlError("M3-1 feedback allowlist is invalid")
        expected = _TEXT_FIELDS | _FLOAT_FIELDS | _INTEGER_FIELDS
        if set(allowed) != expected:
            raise D1ControlError("M3-1 feedback allowlist differs from the executable contract")
        if not isinstance(forbidden, list) or set(allowed).intersection(forbidden):
            raise D1ControlError("M3-1 feedback forbidden fields are invalid")
        if int(value.get("maximum_records", -1)) != 5:
            raise D1ControlError("M3-1 feedback record limit differs")

    def topic_template(self, topic: str) -> dict[str, Any]:
        if topic not in TOPICS:
            raise D1ControlError(f"unknown M3-1 topic: {topic}")
        return dict(self.document["topic_templates"][topic])

    def serialize_feedback(
        self,
        *,
        topic: str,
        current_global_ordinal: int,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if topic not in TOPICS:
            raise D1ControlError(f"unknown M3-1 feedback topic: {topic}")
        contract = self.document["feedback_contract"]
        allowed = tuple(contract["allowed_fields"])
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or set(record) - set(allowed):
                raise D1ControlError("M3-1 feedback contains a non-allowlisted field")
            if record.get("topic") != topic:
                raise D1ControlError("M3-1 feedback must remain within one topic")
            attempt_id = record.get("attempt_id")
            ordinal = record.get("global_ordinal")
            if (
                not isinstance(attempt_id, str)
                or not attempt_id
                or attempt_id in seen
                or isinstance(ordinal, bool)
                or not isinstance(ordinal, int)
                or ordinal >= current_global_ordinal
            ):
                raise D1ControlError("M3-1 feedback identity or order is invalid")
            for field in _TEXT_FIELDS:
                value = record.get(field)
                if value is not None and (
                    not isinstance(value, str)
                    or len(value) > 1000
                    or any(ord(character) < 32 for character in value)
                ):
                    raise D1ControlError(f"M3-1 feedback text is invalid: {field}")
            for field in _FLOAT_FIELDS:
                value = record.get(field)
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or not -1 <= float(value) <= 1
                ):
                    raise D1ControlError(f"M3-1 feedback number is invalid: {field}")
            for field in _INTEGER_FIELDS - {"global_ordinal"}:
                value = record.get(field)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                ):
                    raise D1ControlError(f"M3-1 feedback integer is invalid: {field}")
            seen.add(attempt_id)
            normalized.append({field: record.get(field) for field in allowed})
        normalized.sort(key=lambda row: (int(row["global_ordinal"]), str(row["attempt_id"])))
        if len(normalized) > int(contract["maximum_records"]):
            raise D1ControlError("M3-1 feedback exceeds the frozen record limit")
        return normalized
