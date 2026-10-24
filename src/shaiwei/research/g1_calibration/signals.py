"""对照信号构造与执行计划：每条路线一个确定性构造，全部回到真实候选的中性化口径。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from shaiwei.config import Settings
from shaiwei.research.factor_portfolio import backtest_signal
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_calibration.evidence import Backtester
from shaiwei.research.g1_calibration.protocol import ProtocolError, ProtocolIdentity
from shaiwei.research.g1_pipeline import BaselineWindow, ResearchData

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?")
RATIONALE = {
    "R1": "标定正控：基线同一标签与独立噪声的合成混合，含未来信息，不具经济含义，仅测门的检出能力。",
    "R2": "标定诊断：与 R1 同一合成信号，跳过 90/10 混合直接组合，量化混合对信号的稀释。",
    "R3": "公开对照：过去 20 个交易日累计收益取负的短期反转，A 股文献记录为强异象，只报告。",
    "R4": "公开对照：过去 20 个交易日日收益波动取负的低波动，A 股文献记录为显著异象，只报告。",
    "R5": "公开对照：剔除最近 20 日的 12 个月动量，A 股文献记录为不存在，预期不通过，只报告。",
    "N1": "阴性对照：每日截面独立标准正态噪声，不含任何信息，用于估计门的误放率。",
    "N2": "阴性对照：R3 因子值在每日截面内随机打乱，保留分布与时间结构、切断股票对应关系。",
}


@dataclass(frozen=True)
class Unit:
    route: str
    strength: float | None = None
    seed: int | None = None


@dataclass(frozen=True)
class ControlSignal:
    residual: pd.Series
    daily_ic: pd.Series
    formula: str
    tokens: int
    nodes: int
    pit: bool
    shift: bool
    construction: dict[str, object]


@dataclass
class RunContext:
    settings: Settings
    protocol: ProtocolIdentity
    research: ResearchData
    r5_stock_data: object
    baselines: list[BaselineWindow]
    code_hash: str
    data_hash: str
    backtest: Backtester = backtest_signal
    expression_values: Callable[[str, object], pd.Series] = controls.raw_expression_values
    audit: Callable[[str], object] | None = None
    cache: dict[str, object] = field(default_factory=dict)

    @property
    def min_cross_section(self) -> int:
        return self.settings.alphagen_benchmark.min_cross_section

    @property
    def discovery(self) -> tuple[object, object]:
        calibration = self.protocol.config.calibration
        return calibration.discovery_start, calibration.discovery_end


def plan_cells(protocol: ProtocolIdentity, noise_seeds: int) -> list[list[Unit]]:
    config = protocol.config
    allowed = {len(config.routes["N1"].seed_values())} | {step["N1"] for step in config.budget.reduction_order}
    if noise_seeds not in allowed or any(step["N1"] != step["N2"] for step in config.budget.reduction_order):
        raise ProtocolError(f"noise seeds must follow the frozen reduction order {sorted(allowed, reverse=True)}")
    seeds = config.routes["R1"].seed_values()
    cells = []
    for strength in config.calibration.target_mean_rank_ic:
        cells.append([Unit("R1", strength, seed) for seed in seeds])
        cells.append([Unit("R2", strength, seed) for seed in seeds])
    cells.extend([[Unit("R3")], [Unit("R4")], [Unit("R5")]])
    for route in ("N1", "N2"):
        cells.append([Unit(route, None, seed) for seed in config.routes[route].seed_values()[:noise_seeds]])
    return cells


def _audit(ctx: RunContext, expression: str) -> object:
    if ctx.audit is not None:
        return ctx.audit(expression)
    from shaiwei.research.alphagen_expression import audit_expression

    return audit_expression(expression)


def _cached(ctx: RunContext, key: str, build: Callable[[], object]) -> object:
    if key not in ctx.cache:
        ctx.cache[key] = build()
    return ctx.cache[key]


def _formula_signal(formula: str, residual: pd.Series, daily_ic: pd.Series, *, pit: bool, shift: bool, **construction: object) -> ControlSignal:
    tokens = len(_TOKEN.findall(formula))
    return ControlSignal(residual, daily_ic, formula, tokens, tokens, pit, shift, construction)


def _expression_signal(ctx: RunContext, route: str) -> ControlSignal:
    def build() -> ControlSignal:
        expression = controls.ROUTE_EXPRESSIONS[route]
        stock_data = ctx.r5_stock_data if route == "R5" else ctx.research.stock_data
        raw = ctx.expression_values(expression, stock_data)
        residual, daily_ic = controls.neutralize(raw, ctx.research, min_cross_section=ctx.min_cross_section)
        audit = _audit(ctx, expression)
        return ControlSignal(
            residual, daily_ic, expression, audit.expression_tokens, audit.ast_nodes,  # type: ignore[attr-defined]
            audit.pit_sentinel_pass, audit.shift_sentinel_pass, {"raw_rows": len(raw)},  # type: ignore[attr-defined]
        )

    return _cached(ctx, f"signal:{route}", build)  # type: ignore[return-value]


def _blend_signal(ctx: RunContext, strength: float, seed: int) -> ControlSignal:
    def build() -> ControlSignal:
        z_label = _cached(ctx, "z_label", lambda: controls.cross_section_z(ctx.research.labels))
        label_residual = _cached(
            ctx, "label_residual", lambda: controls.neutralize(z_label, ctx.research, min_cross_section=ctx.min_cross_section)[0]
        )
        z_noise = controls.cross_section_z(controls.seeded_normal(z_label.index, seed))  # type: ignore[union-attr]
        noise_residual, _ = controls.neutralize(z_noise, ctx.research, min_cross_section=ctx.min_cross_section)
        tolerance = ctx.protocol.config.calibration.tolerance
        calibration = controls.calibrate_blend(
            target=strength,
            tolerance=tolerance,
            label_residual=label_residual,  # type: ignore[arg-type]
            noise_residual=noise_residual,
            labels=ctx.research.labels,
            discovery=ctx.discovery,  # type: ignore[arg-type]
        )
        raw = controls.blend(z_label, z_noise, calibration.a)  # type: ignore[arg-type]
        residual, daily_ic = controls.neutralize(raw, ctx.research, min_cross_section=ctx.min_cross_section)
        achieved = controls.verify_blend(
            calibration=calibration, residual=residual, daily_ic=daily_ic, label_residual=label_residual,  # type: ignore[arg-type]
            noise_residual=noise_residual, discovery=ctx.discovery, tolerance=tolerance,  # type: ignore[arg-type]
        )
        return _formula_signal(
            "Blend(z(label),z(Normal(seed)),a)", residual, daily_ic, pit=False, shift=False,
            target_mean_rank_ic=strength, a=calibration.a, achieved_discovery_rank_ic=achieved,
            bisection_iterations=calibration.iterations,
        )

    return _cached(ctx, f"signal:blend:{strength}:{seed}", build)  # type: ignore[return-value]


def build_signal(ctx: RunContext, unit: Unit) -> ControlSignal:
    if unit.route in {"R1", "R2"}:
        return _blend_signal(ctx, float(unit.strength), int(unit.seed))  # type: ignore[arg-type]
    if unit.route in controls.ROUTE_EXPRESSIONS:
        return _expression_signal(ctx, unit.route)
    if unit.route == "N1":
        support = _cached(
            ctx, "pit_support", lambda: ctx.expression_values(controls.PIT_SUPPORT_EXPRESSION, ctx.research.stock_data).index
        )
        raw = controls.seeded_normal(support, int(unit.seed))  # type: ignore[arg-type]
        residual, daily_ic = controls.neutralize(raw, ctx.research, min_cross_section=ctx.min_cross_section)
        return _formula_signal("Normal(seed)", residual, daily_ic, pit=True, shift=True)
    if unit.route == "N2":
        r3 = _expression_signal(ctx, "R3")
        r3_raw = _cached(ctx, "r3_raw", lambda: ctx.expression_values(controls.ROUTE_EXPRESSIONS["R3"], ctx.research.stock_data))
        raw = controls.shuffle_within_dates(r3_raw, int(unit.seed))  # type: ignore[arg-type]
        residual, daily_ic = controls.neutralize(raw, ctx.research, min_cross_section=ctx.min_cross_section)
        return _formula_signal(f"Shuffle({r3.formula},seed)", residual, daily_ic, pit=r3.pit, shift=r3.shift)
    raise ProtocolError(f"unknown route: {unit.route}")


