"""TP-F-1 candidate contract: safe AST, ceilings, joint-state signature, and canonical identity rejection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.alphagen_expression import ExpressionSafetyError, audit_expression
from shaiwei.research.tp_f_0b.contract import TPFScope
from shaiwei.research.tp_f_0b.registry import alpha158_expressions, read_allowed
from shaiwei.research.tp_f_0b.signature import SignatureError, SignatureRule, signature
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope
from shaiwei.research.trend_swing.contract import sha256_file

ATTEMPT_LEDGERS = ("d1_v2", "m1", "m3")
ROUTES = ("R3", "R4", "R5")


@dataclass(frozen=True)
class IdentityIndex:
    """Canonical identities a TP-F-1 candidate may not equal (TP-F-0B registry + extension)."""

    canonical: frozenset[str]
    sealed_raw_hashes: frozenset[str]
    d1_v2_joint_state: frozenset[str]
    source_counts: dict[str, int]

    @classmethod
    def build(cls, rule: SignatureRule, *, alpha158: Callable[[], list[str]] = alpha158_expressions,
              root: Path = PROJECT_ROOT) -> "IdentityIndex":
        from shaiwei.research.g1_calibration.controls import ROUTE_EXPRESSIONS

        tpf0b = TPFScope.load(root)
        sealed = tpf0b.document["identity_registry"]["sealed_base"]
        sealed_path = root / sealed["path"]
        if sha256_file(sealed_path) != sealed["sha256"]:
            raise TPF1Error("TP-F-1 sealed RF-0B registry differs")
        sealed_hashes = frozenset(json.loads(sealed_path.read_text(encoding="utf-8"))["expression_hash_union"])
        canonical: set[str] = set()
        joint: set[str] = set()
        counts: dict[str, int] = {}

        def add(source: str, texts: Iterable[str], *, fail_closed: bool) -> None:
            parsed = 0
            for text in texts:
                try:
                    item = signature(text, rule)
                except SignatureError:
                    if fail_closed:
                        raise TPF1Error(f"TP-F-1 baseline identity is unparseable in {source}")
                    continue
                parsed += 1
                canonical.add(item.canonical_sha256)
                if source == "attempt_ledger_d1_v2" and item.joint_state:
                    joint.add(item.canonical_sha256)
            counts[source] = parsed

        add("alpha158", alpha158(), fail_closed=True)
        for name in ATTEMPT_LEDGERS:
            row = tpf0b.document["frozen_inputs"]["identity_ledgers"][name]
            if sha256_file(root / row["path"]) != row["sha256"]:
                raise TPF1Error(f"TP-F-1 identity ledger differs: {row['path']}")
            texts = [r["canonical_expression"] for r in read_allowed(root / row["path"], ["canonical_expression"]) if r["canonical_expression"]]
            add(f"attempt_ledger_{name}", texts, fail_closed=False)
        add("public_routes", [ROUTE_EXPRESSIONS[route] for route in ROUTES], fail_closed=True)
        counts["ts_v5_semantic_signatures_comparable_to_expressions"] = 0
        return cls(frozenset(canonical), sealed_hashes, frozenset(joint), counts)


def _placeholder(rationale: str, expression: str) -> bool:
    text = rationale.strip()
    return text == expression.strip() or len(set(text)) < 8


def validate_candidate(
    scope: TPF1Scope,
    index: IdentityIndex,
    rule: SignatureRule,
    expression_text: object,
    rationale: object,
    *,
    seen_in_batch: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Returns QUALIFIED or the first failure class; cheap checks run first. Never raises on candidate content."""
    contract = scope.document["candidate_contract"]
    result: dict[str, Any] = {"status": "", "expression": expression_text if isinstance(expression_text, str) else ""}

    def fail(name: str, detail: str = "") -> dict[str, Any]:
        return {**result, "status": name, "detail": detail[:200]}

    if not isinstance(expression_text, str) or not expression_text.strip():
        return fail("EMPTY_EXPRESSION")
    if not isinstance(rationale, str) or len(rationale.strip()) < int(contract["economic_rationale_minimum_chars"]) \
            or _placeholder(rationale, expression_text):
        return fail("RATIONALE_MISSING_OR_PLACEHOLDER")
    try:
        audit = audit_expression(expression_text)
    except ExpressionSafetyError as exc:
        return fail("UNSAFE_AST", str(exc))
    result.update(normalized_expression=audit.normalized_expression, expression_tokens=audit.expression_tokens,
                  ast_nodes=audit.ast_nodes, max_lookback_days=audit.max_lookback_days,
                  required_backtrack_days=audit.required_backtrack_days)
    if not (audit.pit_sentinel_pass and audit.shift_sentinel_pass):
        return fail("LEAKAGE_SENTINEL")
    if audit.expression_tokens > int(contract["maximum_expression_tokens"]):
        return fail("TOKEN_CEILING")
    if audit.ast_nodes > int(contract["maximum_ast_nodes"]):
        return fail("AST_NODE_CEILING")
    if audit.required_backtrack_days > int(contract["maximum_required_backtrack_trade_days"]):
        return fail("BACKTRACK_CEILING")
    try:
        item = signature(audit.normalized_expression, rule)
    except SignatureError as exc:
        return fail("SIGNATURE_UNPARSEABLE", str(exc))
    result.update(canonical=item.canonical, canonical_sha256=item.canonical_sha256,
                  trend_components=item.trend_components, pullback_components=item.pullback_components)
    if not item.joint_state:
        return fail("NOT_JOINT_STATE")
    if hashlib.sha256(audit.normalized_expression.encode()).hexdigest() in index.sealed_raw_hashes:
        return fail("DUPLICATE_SEALED_REGISTRY")
    if item.canonical_sha256 in index.canonical:
        return fail("DUPLICATE_CANONICAL_IDENTITY", "d1_v2_joint_state" if item.canonical_sha256 in index.d1_v2_joint_state else "")
    if item.canonical_sha256 in seen_in_batch:
        return fail("DUPLICATE_WITHIN_BATCH")
    return {**result, "status": "QUALIFIED", "economic_rationale": rationale.strip()}
