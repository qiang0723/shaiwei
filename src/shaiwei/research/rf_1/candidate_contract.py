"""RF-1 candidate contract: safe AST, mandatory open/close references, registry dedup."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from shaiwei.research.alphagen_expression import ExpressionSafetyError, audit_expression
from shaiwei.research.rf_1.contract import (
    RF1Error,
    RF1Scope,
    SEALED_REGISTRY_PATH,
    SEALED_REGISTRY_SHA256,
    sha256_file,
)


def _sealed_expression_hashes() -> frozenset[str]:
    if not SEALED_REGISTRY_PATH.is_file() or sha256_file(SEALED_REGISTRY_PATH) != SEALED_REGISTRY_SHA256:
        raise RF1Error("RF-1 sealed identity registry differs")
    try:
        document = json.loads(SEALED_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RF1Error("RF-1 sealed identity registry is invalid") from exc
    return frozenset(document["expression_hash_union"])


def validate_candidate(
    scope: RF1Scope, expression_text: str, economic_rationale: str
) -> dict[str, Any]:
    """Fail-closed validation of one candidate against the frozen contract and registry."""
    contract = scope.document["candidate_contract"]
    if not isinstance(expression_text, str) or not expression_text.strip():
        raise RF1Error("RF-1 candidate expression is empty")
    if not isinstance(economic_rationale, str) or len(economic_rationale.strip()) < 16:
        raise RF1Error("RF-1 candidate economic rationale is missing or placeholder-grade")
    try:
        audit = audit_expression(expression_text)
    except ExpressionSafetyError as exc:
        raise RF1Error(f"RF-1 candidate AST is unsafe: {exc}") from exc
    normalized = audit.normalized_expression
    if "$open" not in normalized or "$close" not in normalized:
        raise RF1Error("RF-1 candidate must reference both $open and $close")
    if audit.expression_tokens > int(contract["maximum_expression_tokens"]):
        raise RF1Error("RF-1 candidate exceeds the token ceiling")
    if audit.ast_nodes > int(contract["maximum_ast_nodes"]):
        raise RF1Error("RF-1 candidate exceeds the AST-node ceiling")
    if audit.max_lookback_days > int(contract["maximum_lookback_trade_days"]):
        raise RF1Error("RF-1 candidate exceeds the 50-day lookback ceiling")
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    if digest in _sealed_expression_hashes():
        raise RF1Error("RF-1 candidate duplicates the sealed identity registry")
    return {
        "normalized_expression": normalized,
        "expression_sha256": digest,
        "expression_tokens": audit.expression_tokens,
        "ast_nodes": audit.ast_nodes,
        "max_lookback_days": audit.max_lookback_days,
        "references_open_and_close": True,
        "registry_dedup": "PASS",
    }
