"""Deterministic narrative-to-DSL checks for newly generated factor candidates."""

from __future__ import annotations

import re

from shaiwei.research.alphagen_expression import ALLOWED_FEATURES, ALLOWED_OPERATOR_NAMES
from shaiwei.research.llm_factor import CandidateProposal


_DSL_CALL = re.compile(
    rf"(?<![A-Za-z0-9_])(?:{'|'.join(sorted(map(re.escape, ALLOWED_OPERATOR_NAMES), key=len, reverse=True))})\s*\("
)
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?")
_SEALED_RESULT = re.compile(
    r"20(?:23|24|25)|验证期|压力期|前瞻|准入结果|生产信号|\bG1\b|\bW[1-6]\b",
    re.IGNORECASE,
)
_VARIATION = re.compile(
    r"改用|替代|或者|另一(?:个|条|种)?|备选|候选变体|参数变体|调整窗口|不同窗口|"
    r"可(?:以)?调参|alternative|instead|variant|tune|replace",
    re.IGNORECASE,
)
_PERFORMANCE_CLAIM = re.compile(
    r"(?:已经|已|能够|可以|预计|将会?|必然)(?:显著|稳定|持续)?"
    r"(?:盈利|获利|跑赢|提高收益|降低回撤|通过(?:回测|验证|G1|准入)|适合实盘|用于生产)|"
    r"\b(?:will|can|has|is)\s+(?:outperform|profitable|passed|admitted|production.ready)\b",
    re.IGNORECASE,
)


def _narrative(proposal: CandidateProposal) -> str:
    risks = "\n".join(proposal.known_failure_risks)
    return "\n".join((proposal.hypothesis, proposal.economic_rationale_draft, risks))


def validate_candidate_semantics(proposal: CandidateProposal) -> str | None:
    """Return a stable reason code when prose expands or contradicts the sole DSL candidate."""
    narrative = _narrative(proposal)
    if _SEALED_RESULT.search(narrative):
        return "sealed_or_admission_result_reference"
    if _PERFORMANCE_CLAIM.search(narrative):
        return "performance_or_production_claim"
    if _DSL_CALL.search(narrative):
        return "dsl_expression_in_narrative"
    if _VARIATION.search(narrative):
        return "formula_or_parameter_variant_in_narrative"

    expression_numbers = set(_NUMBER.findall(proposal.expression))
    narrative_numbers = set(_NUMBER.findall(narrative))
    if narrative_numbers - expression_numbers:
        return "unbound_numeric_parameter_in_narrative"

    expression_lower = proposal.expression.lower()
    for feature in ALLOWED_FEATURES:
        normalized = feature.removeprefix("$").lower()
        token = rf"(?<![A-Za-z0-9_]){re.escape(normalized)}(?![A-Za-z0-9_])"
        if re.search(token, narrative, re.IGNORECASE):
            if re.search(token, expression_lower) is None:
                return "unbound_feature_in_narrative"
    return None
