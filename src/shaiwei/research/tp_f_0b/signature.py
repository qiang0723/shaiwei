"""Canonical expression AST and the frozen trend x pullback joint-state signature (protocol §5.3)."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable, Iterator, Mapping

from shaiwei.research.alphagen_expression import normalize_expression_text


FEATURES = frozenset({"open", "close", "high", "low", "volume", "vwap"})
EPSILON = 1e-6  # Alpha158 在分母上加 1e-12；|c| ≤ 1e-6 的加法常数按"epsilon additions ignored"去掉
_FEATURE_TOKEN = re.compile(r"\$([A-Za-z_]+)")
_DAY_SUFFIX = re.compile(r"\b(\d+)d\b")
_BINARY = {ast.Add: "Add", ast.Sub: "Sub", ast.Mult: "Mul", ast.Div: "Div"}
_COMPARE = {ast.Gt: "Gt", ast.GtE: "Ge", ast.Lt: "Lt", ast.LtE: "Le", ast.Eq: "Eq", ast.NotEq: "Ne"}
_COMMUTATIVE = frozenset({"Add", "Mul"})


class SignatureError(ValueError):
    """Expression cannot be canonicalized."""


@dataclass(frozen=True)
class Node:
    kind: str  # feature | constant | call
    name: str = ""
    value: float = 0.0
    args: tuple["Node", ...] = ()

    def text(self) -> str:
        if self.kind == "feature":
            return f"${self.name}"
        if self.kind == "constant":
            return format(self.value, ".12g")
        return f"{self.name}({','.join(arg.text() for arg in self.args)})"


def _convert(node: ast.AST) -> Node:
    if isinstance(node, ast.Name):
        if node.id not in FEATURES:
            raise SignatureError(f"unknown name: {node.id}")
        return Node("feature", node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Node("constant", value=float(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _convert(node.operand)
        if operand.kind == "constant":
            return Node("constant", value=-operand.value)
        return Node("call", "Mul", args=(Node("constant", value=-1.0), operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        return Node("call", _BINARY[type(node.op)], args=(_convert(node.left), _convert(node.right)))
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE:
        return Node("call", _COMPARE[type(node.ops[0])], args=(_convert(node.left), _convert(node.comparators[0])))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        args = tuple(_convert(arg) for arg in node.args)
        if node.func.id == "Constant":
            if len(args) != 1 or args[0].kind != "constant":
                raise SignatureError("Constant() must wrap one number")
            return args[0]
        return Node("call", node.func.id, args=args)
    raise SignatureError(f"unsupported expression syntax: {type(node).__name__}")


def _normalize(node: Node) -> Node:
    if node.kind != "call":
        return node
    args = tuple(_normalize(arg) for arg in node.args)
    if node.name == "Add" and len(args) == 2:
        kept = [arg for arg in args if not (arg.kind == "constant" and abs(arg.value) <= EPSILON)]
        if len(kept) == 1:
            return kept[0]
    if node.name in _COMMUTATIVE:
        args = tuple(sorted(args, key=Node.text))
    return Node("call", node.name, args=args)


def parse(expression_text: str) -> Node:
    """AlphaGen prefix ($close, 20d, Constant()) and qlib infix (Alpha158) into one canonical tree."""
    source = _FEATURE_TOKEN.sub(r"\1", _DAY_SUFFIX.sub(r"\1", normalize_expression_text(expression_text)))
    try:
        tree = ast.parse(source, mode="eval").body
    except SyntaxError as exc:
        raise SignatureError(f"expression is not parseable: {expression_text!r}") from exc
    return _normalize(_convert(tree))


def _window(node: Node) -> int | None:
    if node.kind == "constant" and float(node.value).is_integer() and node.value >= 1:
        return int(node.value)
    return None


def _anchor_window(node: Node, features: frozenset[str], anchors: frozenset[str]) -> int | None:
    if node.kind == "call" and node.name in anchors and len(node.args) == 2:
        inner, window = node.args
        if inner.kind == "feature" and inner.name in features:
            return _window(window)
    return None


def _ref_lag(node: Node, prices: frozenset[str]) -> int | None:
    if node.kind == "call" and node.name == "Ref" and len(node.args) == 2:
        inner, lag = node.args
        if inner.kind == "feature" and inner.name in prices:
            return _window(lag)
    return None


@dataclass(frozen=True)
class SignatureRule:
    prices: frozenset[str]
    anchors: frozenset[str]
    trend_minimum: int = 20  # 冻结原文 trend_component "window >= 20 ... lag >= 20"
    pullback_window: tuple[int, int] = (2, 10)  # 冻结原文 pullback "2 <= window <= 10 (Ref excluded)"

    @classmethod
    def from_protocol(cls, rule: Mapping[str, Any]) -> "SignatureRule":
        prices = frozenset(name.removeprefix("$") for name in rule["price_features"])
        if not prices <= FEATURES or "volume" in prices:
            raise SignatureError("joint-state price features differ from the grammar")
        return cls(prices=prices, anchors=frozenset(rule["anchor_operators"]))

    def _pairs(self, node: Node) -> Iterator[tuple[Node, Node]]:
        if node.kind == "call" and node.name in {"Div", "Sub"} and len(node.args) == 2:
            first, second = node.args
            yield first, second
            yield second, first

    def is_trend(self, node: Node) -> bool:
        for price, anchor in self._pairs(node):
            if price.kind == "feature" and price.name in self.prices:
                window = _anchor_window(anchor, self.prices, self.anchors)
                lag = _ref_lag(anchor, self.prices)
                if (window is not None and window >= self.trend_minimum) or (lag is not None and lag >= self.trend_minimum):
                    return True
        return False

    def _volume_window(self, node: Node) -> int | None:
        if node.kind == "feature" and node.name == "volume":
            return 1
        return _anchor_window(node, frozenset({"volume"}), self.anchors)

    def is_pullback(self, node: Node) -> bool:
        low, high = self.pullback_window
        for price, anchor in self._pairs(node):
            if price.kind == "feature" and price.name in self.prices:
                window = _anchor_window(anchor, self.prices, self.anchors)
                if window is not None and low <= window <= high:
                    return True
        if node.kind == "call" and node.name in {"Div", "Sub"} and len(node.args) == 2:
            windows = [self._volume_window(arg) for arg in node.args]
            if None not in windows and windows[0] != windows[1]:
                return True
            if node.name == "Div" and [arg.text() for arg in node.args] == ["Sub($close,$low)", "Sub($high,$low)"]:
                return True
        return False


def _walk(node: Node, path: tuple[int, ...] = ()) -> Iterator[tuple[tuple[int, ...], Node]]:
    yield path, node
    for index, arg in enumerate(node.args):
        yield from _walk(arg, (*path, index))


def _disjoint(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return left[: len(right)] != right and right[: len(left)] != left


@dataclass(frozen=True)
class Signature:
    canonical: str
    canonical_sha256: str
    trend_components: int
    pullback_components: int
    joint_state: bool


def signature(expression_text: str, rule: SignatureRule) -> Signature:
    root = parse(expression_text)
    nodes = list(_walk(root))
    trend = [path for path, node in nodes if rule.is_trend(node)]
    pullback = [path for path, node in nodes if rule.is_pullback(node)]
    canonical = root.text()
    return Signature(
        canonical=canonical,
        canonical_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        trend_components=len(trend),
        pullback_components=len(pullback),
        joint_state=any(_disjoint(t, p) for t in trend for p in pullback),
    )


def census(expressions: Iterable[str], rule: SignatureRule, *, fail_closed: bool) -> dict[str, int]:
    """Counts only. A baseline source fails closed: an unparseable baseline expression cannot be ruled out."""
    total = failures = trend = pullback = joint = 0
    canonical: set[str] = set()
    for text in expressions:
        total += 1
        try:
            item = signature(text, rule)
        except SignatureError:
            if fail_closed:
                raise
            failures += 1
            continue
        canonical.add(item.canonical_sha256)
        trend += item.trend_components > 0
        pullback += item.pullback_components > 0
        joint += item.joint_state
    return {
        "expressions": total,
        "parse_failures": failures,
        "unique_canonical": len(canonical),
        "with_trend_component": trend,
        "with_pullback_component": pullback,
        "joint_state": joint,
    }
