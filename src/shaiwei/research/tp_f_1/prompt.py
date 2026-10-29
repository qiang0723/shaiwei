"""Frozen TP-F-1 prompt: request construction and strict response parsing (no effect information ever enters)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.alphagen_expression import ALLOWED_FEATURES, ALLOWED_OPERATOR_NAMES
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope

PROMPT_RELATIVE = "config/tp_f_1_prompt_v1.yaml"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class PromptBundle:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, scope: TPF1Scope, root: Path = PROJECT_ROOT) -> "PromptBundle":
        path = root / PROMPT_RELATIVE
        payload = path.read_bytes()
        document = yaml.safe_load(payload)
        contract, batch = scope.document["candidate_contract"], scope.document["batch_contract"]
        grammar, limits, request = document["grammar"], document["constraints"], document["request"]
        consistent = (
            document.get("contains_effect_information") is False
            and document.get("protocol_id") == scope.document["protocol_id"]
            and set(grammar["features"]) == set(contract["allowed_features"]) == ALLOWED_FEATURES
            and limits["maximum_window_days_per_operator"] == contract["maximum_window_days_per_operator"]
            and limits["maximum_total_backtrack_trade_days"] == contract["maximum_required_backtrack_trade_days"]
            and limits["maximum_expression_tokens"] == contract["maximum_expression_tokens"]
            and limits["maximum_ast_nodes"] == contract["maximum_ast_nodes"]
            and limits["economic_rationale_minimum_chars"] == contract["economic_rationale_minimum_chars"]
            and request["model"] == batch["model"]
        )
        if not consistent:
            raise TPF1Error("TP-F-1 prompt differs from the frozen protocol")
        return cls(document, hashlib.sha256(payload).hexdigest())

    def build_request(self, *, ordinal: int, already_proposed: list[str]) -> dict[str, Any]:
        """Each attempt sees only the canonical expressions already proposed in this batch, never any result."""
        document = self.document
        task = {
            "attempt_ordinal": ordinal,
            "mechanism": document["mechanism"],
            "allowed_features": sorted(ALLOWED_FEATURES),
            "allowed_operators": sorted(ALLOWED_OPERATOR_NAMES),
            "window_suffix": document["grammar"]["window_suffix"],
            "example_syntax": document["grammar"]["example_syntax"],
            "example_is_syntax_only_and_is_not_a_joint_state": True,
            "constraints": document["constraints"],
            "already_proposed_in_this_batch": list(already_proposed),
            "output_schema": document["output_schema"],
            "prompt_sha256": self.sha256,
        }
        request = document["request"]
        body = {
            "model": request["model"],
            "messages": [{"role": "system", "content": document["system_prompt"]}, {"role": "user", "content": canonical_json(task)}],
            "thinking": {"type": request["thinking"]},
            "reasoning_effort": request["reasoning_effort"],
            "response_format": {"type": request["response_format"]},
            "max_tokens": request["max_tokens"],
            "tools": [],
            "stream": False,
        }
        if len(canonical_json(body).encode("utf-8")) + 1024 > int(request["maximum_prompt_tokens_per_attempt"]):
            raise TPF1Error("TP-F-1 request exceeds the conservative frozen input-token bound")
        return body


def parse_response(content: str) -> tuple[str, str] | None:
    """Exactly {expression, economic_rationale} as strings; anything else is a RESPONSE_SCHEMA failure (None)."""
    try:
        value = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {"expression", "economic_rationale"}:
        return None
    if not all(isinstance(value[key], str) for key in value):
        return None
    return value["expression"], value["economic_rationale"]
