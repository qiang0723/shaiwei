"""正控与阴性对照的因子构造，以及只看发现期的 R1 强度 `a` 标定（协议 §3、§4）。

全部原始因子都走与真实候选相同的中性化与日频 RankIC 口径（`neutralize` 与
`g1_pipeline.evaluate_factor_panel` 表达式求值之后的步骤一致，由等价性测试钉住）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from shaiwei.benchmark.fitness import neutralized_factor_values
from shaiwei.research.factor_portfolio import daily_rank_ic
from shaiwei.research.g1_calibration.protocol import PositiveControlConfig, ProtocolError
from shaiwei.research.g1_pipeline import ResearchData, _series

# 公开对照的表达式由冻结配置的回看/方向参数手写而来；R5 用五层 Ref(·,50) 叠出 250 日，
# 以便原样通过与真实候选相同的白名单解析和 shift 哨兵（单节点窗口上限 50）。
ROUTE_EXPRESSIONS = {
    "R3": "Mul(Sub(Div(close,Ref(close,20)),Constant(1.0)),Constant(-1.0))",
    "R4": "Mul(Std(Sub(Div(close,Ref(close,1)),Constant(1.0)),20),Constant(-1.0))",
    "R5": "Sub(Div(Ref(close,20),Ref(Ref(Ref(Ref(Ref(close,50),50),50),50),50)),Constant(1.0))",
}
_EXPECTED_ROUTE_PARAMETERS = {
    "R3": ("short_term_reversal", 20, None, -1),
    "R4": ("short_term_volatility", 20, None, -1),
    "R5": ("momentum_12_1", 250, 20, 1),
}
R5_BACKTRACK_DAYS = 260  # 250 日回看 + 余量；研究主数据只预热 100 日，R5 单独建数据集
PIT_SUPPORT_EXPRESSION = "close"  # N1 的截面支撑：当日有收盘价，不借用未来标签是否存在
# 线性校验容差：真实设计（31 个行业哑变量 + 对数市值）上分开求最小二乘的数值差实测最大 3.7e-7（2026-10-24 诊断，
# 未涉及任何门或结果）；结构性非线性会差到 1e-1 量级，1e-5 足以区分。最终评估只用真实路径残差，且须落在目标容差内。
LINEARITY_ATOL = 1e-5


class CalibrationError(RuntimeError):
    pass


def verify_route_expressions(config: PositiveControlConfig) -> None:
    for route, (construction, lookback, skip, sign) in _EXPECTED_ROUTE_PARAMETERS.items():
        spec = config.routes[route]
        actual = (spec.construction, spec.lookback_trade_days, spec.skip_recent_trade_days, spec.sign)
        if actual != (construction, lookback, skip, sign):
            raise ProtocolError(f"{route} parameters differ from the hand-written expression: {actual}")


def raw_expression_values(expression_text: str, stock_data: object) -> pd.Series:
    from shaiwei.research.alphagen_expression import parse_safe_expression

    expression = parse_safe_expression(expression_text)
    frame = stock_data.make_dataframe(expression.evaluate(stock_data), columns=["factor"])  # type: ignore[attr-defined]
    return _series(frame, "factor").dropna()


def neutralize(raw: pd.Series, research: ResearchData, *, min_cross_section: int) -> tuple[pd.Series, pd.Series]:
    observations = (
        raw.rename("factor")
        .reset_index()
        .merge(research.labels.rename("label").reset_index(), on=["datetime", "instrument"])
        .rename(columns={"datetime": "trade_date"})
        .merge(research.exposures, on=["trade_date", "instrument"])
    )
    residual = neutralized_factor_values(observations, min_cross_section=min_cross_section)
    residual.index = residual.index.set_names(["datetime", "instrument"])
    daily_ic = daily_rank_ic(residual, research.labels)
    if daily_ic.empty:
        raise CalibrationError("control factor has no valid neutralized daily RankIC")
    return residual.sort_index(), daily_ic.sort_index()


def neutralize_pit(raw: pd.Series, research: ResearchData, *, min_cross_section: int) -> tuple[pd.Series, pd.Series]:
    """g1-v2 口径：残差只用当日 PIT 支撑（不与标签合并），标签只在计算 IC 时使用。"""
    from shaiwei.research.g1_v2 import neutralized_pit

    observations = (
        raw.rename("factor")
        .reset_index()
        .rename(columns={"datetime": "trade_date"})
        .merge(research.exposures, on=["trade_date", "instrument"])
    )
    residual = neutralized_pit(observations, min_cross_section=min_cross_section)
    residual.index = residual.index.set_names(["datetime", "instrument"])
    daily_ic = daily_rank_ic(residual, research.labels)
    if daily_ic.empty:
        raise CalibrationError("control factor has no valid neutralized daily RankIC")
    return residual.sort_index(), daily_ic.sort_index()


def baseline_copy(predictions: pd.Series, seed: int, weight: float) -> pd.Series:
    """N3：f = w·z(基线分数) + √(1−w²)·z(噪声)，只在基线有 OOS 分数的日期存在。"""
    z_base = cross_section_z(predictions)
    z_noise = cross_section_z(seeded_normal(z_base.index, seed))
    return blend(z_base, z_noise, weight)


def cross_section_z(values: pd.Series) -> pd.Series:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    grouped = clean.groupby(level="datetime")
    centered = clean - grouped.transform("mean")
    scale = centered.pow(2).groupby(level="datetime").transform("mean").pow(0.5)
    return (centered / scale.where(scale > 0)).dropna()


def seeded_normal(index: pd.MultiIndex, seed: int) -> pd.Series:
    """按排序后的 (datetime, instrument) 顺序抽样，同种子逐位可复现。"""
    ordered = index.sort_values()
    rng = np.random.default_rng(seed)
    return pd.Series(rng.standard_normal(len(ordered)), index=ordered, name="factor")


def shuffle_within_dates(values: pd.Series, seed: int) -> pd.Series:
    """N2：保留每日分布与时间结构，切断股票与因子值的对应关系。"""
    ordered = values.dropna().sort_index()
    dates = ordered.index.get_level_values("datetime")
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    stops = np.r_[starts[1:], len(ordered)]
    rng = np.random.default_rng(seed)
    shuffled = ordered.to_numpy(copy=True)
    for start, stop in zip(starts, stops, strict=True):
        shuffled[start:stop] = rng.permutation(shuffled[start:stop])
    return pd.Series(shuffled, index=ordered.index, name="factor")


def blend(z_label: pd.Series, z_noise: pd.Series, a: float) -> pd.Series:
    if not 0 <= a < 1:
        raise CalibrationError(f"blend weight must be in [0,1): {a}")
    joined = pd.concat([z_label.rename("label"), z_noise.rename("noise")], axis=1, join="inner").dropna()
    return (a * joined["label"] + math.sqrt(1.0 - a * a) * joined["noise"]).rename("factor")


def _discovery(series: pd.Series, start: date, end: date) -> pd.Series:
    dates = series.index.get_level_values("datetime")
    return series.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]


@dataclass(frozen=True)
class BlendCalibration:
    target: float
    a: float
    predicted_ic: float
    iterations: int


def calibrate_blend(
    *,
    target: float,
    tolerance: float,
    label_residual: pd.Series,
    noise_residual: pd.Series,
    labels: pd.Series,
    discovery: tuple[date, date],
    max_iterations: int = 60,
) -> BlendCalibration:
    """中性化对因子线性且两分量有效行相同，故 res(a·zL+b·zN)=a·res(zL)+b·res(zN)，二分只需重排序。"""
    start, end = discovery
    joined = pd.concat(
        [_discovery(label_residual, start, end).rename("label"), _discovery(noise_residual, start, end).rename("noise")],
        axis=1,
        join="inner",
    ).dropna()
    window_labels = _discovery(labels, start, end)

    def mean_ic(a: float) -> float:
        combined = a * joined["label"] + math.sqrt(1.0 - a * a) * joined["noise"]
        values = daily_rank_ic(combined, window_labels)
        if values.empty:
            raise CalibrationError("discovery period has no valid RankIC for calibration")
        return float(values.mean())

    low, high = 0.0, 1.0 - 1e-9
    if mean_ic(high) <= target:
        raise CalibrationError(f"label residual cannot reach target RankIC {target}")
    for iteration in range(1, max_iterations + 1):
        middle = (low + high) / 2.0
        value = mean_ic(middle)
        if abs(value - target) <= tolerance / 4.0:
            return BlendCalibration(target=target, a=middle, predicted_ic=value, iterations=iteration)
        low, high = (middle, high) if value < target else (low, middle)
    raise CalibrationError(f"blend calibration did not converge for target {target}")


def verify_blend(
    *,
    calibration: BlendCalibration,
    residual: pd.Series,
    daily_ic: pd.Series,
    label_residual: pd.Series,
    noise_residual: pd.Series,
    discovery: tuple[date, date],
    tolerance: float,
) -> float:
    """用真实中性化路径复算：线性假设不成立或发现期 RankIC 越出容差即失败关闭，不进入评估。"""
    b = math.sqrt(1.0 - calibration.a * calibration.a)
    predicted = (calibration.a * label_residual + b * noise_residual).reindex(residual.index)
    if predicted.isna().any() or float((predicted - residual).abs().max()) > LINEARITY_ATOL:
        raise CalibrationError("neutralization is not linear on the blend support")
    start, end = discovery
    window = daily_ic.loc[(daily_ic.index >= pd.Timestamp(start)) & (daily_ic.index <= pd.Timestamp(end))]
    achieved = float(window.mean())
    if abs(achieved - calibration.target) > tolerance:
        raise CalibrationError(f"achieved discovery RankIC {achieved:.5f} misses target {calibration.target}")
    return achieved
