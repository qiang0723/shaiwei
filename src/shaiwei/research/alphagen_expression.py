"""Safe AlphaGen expression parsing, complexity accounting, and leakage sentinels."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from shaiwei.config import PROJECT_ROOT

VENDOR = PROJECT_ROOT / "vendor" / "alphagen"
ALLOWED_OPERATOR_NAMES = {
    "Abs",
    "Log",
    "Add",
    "Sub",
    "Mul",
    "Div",
    "Greater",
    "Less",
    "Ref",
    "Mean",
    "Sum",
    "Std",
    "Var",
    "Max",
    "Min",
    "Med",
    "Mad",
    "Delta",
    "WMA",
    "EMA",
    "Cov",
    "Corr",
}
ALLOWED_FEATURES = {"$open", "$close", "$high", "$low", "$volume", "$vwap"}
_LEXICAL_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[-+]?\d+(?:\.\d+)?")


class ExpressionSafetyError(ValueError):
    pass


@dataclass(frozen=True)
class ExpressionAudit:
    normalized_expression: str
    expression_tokens: int
    ast_nodes: int
    max_lookback_days: int
    required_backtrack_days: int
    pit_sentinel_pass: bool
    shift_sentinel_pass: bool
    compared_values: int


def _vendor_imports() -> tuple[Any, type, type, type]:
    if not (VENDOR / "alphagen" / "data" / "parser.py").is_file():
        raise ExpressionSafetyError("vendor/alphagen parser is missing")
    vendor_text = str(VENDOR)
    if vendor_text not in sys.path:
        sys.path.insert(0, vendor_text)
    from alphagen.data.expression import DeltaTime, Feature, Operator
    from alphagen.data.parser import parse_expression

    return parse_expression, Operator, Feature, DeltaTime


def normalize_expression_text(expression_text: str) -> str:
    normalized = re.sub(r"\bopen_\b", "open", expression_text.strip())
    if not normalized:
        raise ExpressionSafetyError("expression is empty")
    return normalized


def parse_safe_expression(expression_text: str) -> Any:
    parse_expression, _, _, _ = _vendor_imports()
    try:
        return parse_expression(normalize_expression_text(expression_text))
    except Exception as error:
        raise ExpressionSafetyError(f"expression parse failed: {type(error).__name__}: {error}") from error


def _walk(expression: Any) -> list[Any]:
    nodes = [expression]
    operands = getattr(expression, "operands", ())
    for operand in operands:
        nodes.extend(_walk(operand))
    return nodes


def _required_backtrack(node: Any, delta_time_type: type) -> int:
    operands = tuple(getattr(node, "operands", ()))
    if not operands:
        return 0
    delta = 0
    children = operands
    if isinstance(operands[-1], delta_time_type):
        delta = int(str(operands[-1]).removesuffix("d")) - 1
        children = operands[:-1]
    return max((_required_backtrack(child, delta_time_type) for child in children), default=0) + delta


def audit_structure(expression_text: str) -> tuple[Any, int, int, int, int]:
    expression = parse_safe_expression(expression_text)
    _, Operator, Feature, DeltaTime = _vendor_imports()
    max_lookback = 0
    for node in _walk(expression):
        if isinstance(node, Operator):
            if type(node).__name__ not in ALLOWED_OPERATOR_NAMES:
                raise ExpressionSafetyError(f"operator is outside the GP whitelist: {type(node).__name__}")
        elif isinstance(node, Feature):
            if str(node) not in ALLOWED_FEATURES:
                raise ExpressionSafetyError(f"feature is outside the GP whitelist: {node}")
        elif isinstance(node, DeltaTime):
            value = int(str(node).removesuffix("d"))
            if not 1 <= value <= 50:
                raise ExpressionSafetyError(f"lookback must be within 1..50 days: {value}")
            max_lookback = max(max_lookback, value)
        elif type(node).__name__ != "Constant":
            raise ExpressionSafetyError(f"AST node is outside the GP whitelist: {type(node).__name__}")
    tokens = len(_LEXICAL_TOKEN.findall(normalize_expression_text(expression_text)))
    required_backtrack = _required_backtrack(expression, DeltaTime)
    return expression, tokens, len(_walk(expression)), max_lookback, required_backtrack


class _SyntheticStockData:
    def __init__(self, data: torch.Tensor, *, backtrack: int, future: int, days: int):
        self.data = data
        self.max_backtrack_days = backtrack
        self.max_future_days = future
        self.n_days = days
        self.n_stocks = data.shape[-1]


def _shift_invariance(expression: Any, *, required_backtrack: int) -> tuple[bool, int]:
    backtrack = max(60, required_backtrack + 5)
    short_days = 128
    long_days = 144
    future = 12
    generator = torch.Generator(device="cpu").manual_seed(20260716)
    rows = backtrack + long_days + future
    data = torch.rand((rows, 6, 17), generator=generator, dtype=torch.float64) + 1.0
    # Future observations are deliberately extreme. A forward-looking expression
    # would change the already-computed prefix when these rows become available.
    data[backtrack + short_days :] *= 10_000.0
    short = _SyntheticStockData(
        data[: backtrack + short_days + future].clone(),
        backtrack=backtrack,
        future=future,
        days=short_days,
    )
    long = _SyntheticStockData(data, backtrack=backtrack, future=future, days=long_days)
    try:
        short_values = expression.evaluate(short).detach().cpu().numpy()
        long_values = expression.evaluate(long).detach().cpu().numpy()[:short_days]
    except Exception as error:
        raise ExpressionSafetyError(
            f"synthetic shift sentinel failed to evaluate: {type(error).__name__}: {error}"
        ) from error
    same_nan = np.array_equal(np.isnan(short_values), np.isnan(long_values))
    finite = np.isfinite(short_values) & np.isfinite(long_values)
    compared = int(finite.sum())
    if compared == 0:
        return False, 0
    equal = bool(np.allclose(short_values[finite], long_values[finite], rtol=0.0, atol=1e-12))
    return same_nan and equal, compared


def audit_expression(expression_text: str) -> ExpressionAudit:
    expression, tokens, nodes, max_lookback, required_backtrack = audit_structure(expression_text)
    shift_pass, compared = _shift_invariance(
        expression,
        required_backtrack=required_backtrack,
    )
    return ExpressionAudit(
        normalized_expression=str(expression),
        expression_tokens=tokens,
        ast_nodes=nodes,
        max_lookback_days=max_lookback,
        required_backtrack_days=required_backtrack,
        pit_sentinel_pass=True,
        shift_sentinel_pass=shift_pass,
        compared_values=compared,
    )
