"""Frozen G8 same-risk evaluator.

Inputs are already fee- and tax-adjusted daily total returns.  The evaluator
does not fetch NAVs, choose products, or infer fees; those are evidence-layer
responsibilities and must be completed before a verdict is requested.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from shaiwei.config import G8Evaluation, PROJECT_ROOT, Settings, load


COMPARATOR_PATH = PROJECT_ROOT / "templates" / "fund_comparator.csv"


class G8Error(RuntimeError):
    """Raised when the evidence contract cannot support a G8 verdict."""


@dataclass(frozen=True)
class PairResult:
    fund_code: str
    observations: int
    risk_coverage: float
    strategy_annualized_return: float
    fund_annualized_return: float
    annualized_excess: float
    maximum_strategy_weight: float
    maximum_fund_weight: float


@dataclass(frozen=True)
class G8Result:
    spec_version: str
    as_of: str
    window_start: str
    window_end: str
    status: str
    basket_median_annualized_excess: float | None
    positive_fund_count: int
    positive_subperiod_count: int
    pair_results: tuple[PairResult, ...]
    subperiod_median_excess: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def comparator_codes(path: Path = COMPARATOR_PATH) -> tuple[str, ...]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "代码" not in frame or frame["代码"].duplicated().any():
        raise G8Error("fund comparator must contain unique 代码 values")
    return tuple(frame["代码"].tolist())


def frozen_spec(settings: Settings | None = None) -> dict[str, object]:
    settings = settings or load()
    config = settings.g8_evaluation.model_dump(mode="json")
    payload = {
        "config": config,
        "comparator_codes": list(comparator_codes()),
        "comparator_sha256": hashlib.sha256(COMPARATOR_PATH.read_bytes()).hexdigest(),
        "formula": "pairwise_lagged_60d_volatility_match_without_leverage",
        "verdict": "median_excess>0 and positive_funds>=4 and positive_subperiods>=2/3",
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["spec_sha256"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return payload


def _validate_returns(returns: pd.DataFrame, expected_codes: tuple[str, ...]) -> pd.DataFrame:
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise G8Error("returns index must be a DatetimeIndex")
    if returns.index.has_duplicates or not returns.index.is_monotonic_increasing:
        raise G8Error("returns dates must be unique and increasing")
    expected = {"strategy", *expected_codes}
    if set(returns.columns) != expected:
        raise G8Error(f"returns columns must be exactly {sorted(expected)}")
    numeric = returns.astype(float)
    values = numeric.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise G8Error("returns contain missing or non-finite values; forward fill is forbidden")
    if (values <= -1).any():
        raise G8Error("daily total returns must be greater than -100%")
    return numeric


def _annualized_return(returns: pd.Series, annualization_days: int) -> float:
    if returns.empty:
        raise G8Error("empty return segment")
    wealth = float((1.0 + returns).prod())
    if wealth <= 0:
        raise G8Error("non-positive terminal wealth")
    return wealth ** (annualization_days / len(returns)) - 1.0


def _window_bounds(as_of: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    end = as_of.normalize()
    return end - pd.DateOffset(years=3), end


def _risk_match_pair(
    pair_returns: pd.DataFrame,
    pair_vol: pd.DataFrame,
    *,
    fund_code: str,
    maximum_weight: float,
    residual_cash_daily_return: float,
) -> pd.DataFrame:
    target = pair_vol.min(axis=1)
    strategy_weight = target / pair_vol["strategy"]
    fund_weight = target / pair_vol[fund_code]
    if (strategy_weight > maximum_weight + 1e-12).any() or (
        fund_weight > maximum_weight + 1e-12
    ).any():
        raise G8Error("risk matching attempted to introduce leverage")
    return pd.DataFrame(
        {
            "strategy_weight": strategy_weight,
            "fund_weight": fund_weight,
            "strategy_return": strategy_weight * pair_returns["strategy"]
            + (1.0 - strategy_weight) * residual_cash_daily_return,
            "fund_return": fund_weight * pair_returns[fund_code]
            + (1.0 - fund_weight) * residual_cash_daily_return,
        }
    )


def evaluate(
    returns: pd.DataFrame,
    *,
    as_of: date | pd.Timestamp,
    settings: Settings | None = None,
    expected_codes: tuple[str, ...] | None = None,
) -> G8Result:
    """Evaluate one trailing three-calendar-year G8 window.

    Each pair is independently scaled at t using volatility estimated through
    t-1.  The common target is min(strategy volatility, fund volatility), so
    both weights are in (0, 1] and no hypothetical borrowing is introduced.
    """
    settings = settings or load()
    rule: G8Evaluation = settings.g8_evaluation
    codes = expected_codes or comparator_codes()
    if len(codes) != rule.required_fund_count:
        raise G8Error(f"G8 requires exactly {rule.required_fund_count} frozen funds")
    frame = _validate_returns(returns, codes)
    verdict_date = pd.Timestamp(as_of).normalize()
    first_verdict = pd.Timestamp(rule.comparator_freeze_date) + pd.DateOffset(years=3)
    window_start, window_end = _window_bounds(verdict_date)
    if verdict_date < first_verdict:
        return G8Result(
            spec_version=rule.spec_version,
            as_of=verdict_date.date().isoformat(),
            window_start=window_start.date().isoformat(),
            window_end=window_end.date().isoformat(),
            status="NOT_READY",
            basket_median_annualized_excess=None,
            positive_fund_count=0,
            positive_subperiod_count=0,
            pair_results=(),
            subperiod_median_excess=(),
        )

    annualized_vol = (
        frame.rolling(
            rule.volatility_lookback_days,
            min_periods=rule.volatility_lookback_days,
        ).std(ddof=1)
        * np.sqrt(rule.annualization_days)
    ).shift(1)
    in_window = (frame.index > window_start) & (frame.index <= window_end)
    window_returns = frame.loc[in_window]
    window_vol = annualized_vol.loc[in_window]
    if len(window_returns) < rule.minimum_evaluation_observations:
        raise G8Error(
            f"G8 needs at least {rule.minimum_evaluation_observations} common observations"
        )

    pair_results: list[PairResult] = []
    normalized_pairs: dict[str, tuple[pd.Series, pd.Series]] = {}
    for code in codes:
        pair_vol = window_vol[["strategy", code]]
        valid = (pair_vol >= rule.minimum_annualized_volatility).all(axis=1)
        coverage = float(valid.mean())
        if coverage < rule.minimum_risk_coverage:
            raise G8Error(
                f"{code} risk coverage {coverage:.4f} is below {rule.minimum_risk_coverage:.4f}"
            )
        pair_vol = pair_vol.loc[valid]
        pair_returns = window_returns.loc[valid, ["strategy", code]]
        matched = _risk_match_pair(
            pair_returns,
            pair_vol,
            fund_code=code,
            maximum_weight=rule.maximum_risk_weight,
            residual_cash_daily_return=rule.residual_cash_daily_return,
        )
        strategy_normalized = matched["strategy_return"]
        fund_normalized = matched["fund_return"]
        strategy_return = _annualized_return(strategy_normalized, rule.annualization_days)
        fund_return = _annualized_return(fund_normalized, rule.annualization_days)
        normalized_pairs[code] = (strategy_normalized, fund_normalized)
        pair_results.append(
            PairResult(
                fund_code=code,
                observations=len(strategy_normalized),
                risk_coverage=coverage,
                strategy_annualized_return=strategy_return,
                fund_annualized_return=fund_return,
                annualized_excess=strategy_return - fund_return,
                maximum_strategy_weight=float(matched["strategy_weight"].max()),
                maximum_fund_weight=float(matched["fund_weight"].max()),
            )
        )

    subperiod_medians: list[float] = []
    for number in range(rule.required_subperiods):
        period_start = window_start + pd.DateOffset(years=number)
        period_end = window_start + pd.DateOffset(years=number + 1)
        excesses = []
        for strategy_normalized, fund_normalized in normalized_pairs.values():
            mask = (strategy_normalized.index > period_start) & (
                strategy_normalized.index <= period_end
            )
            strategy_period = strategy_normalized.loc[mask]
            fund_period = fund_normalized.loc[mask]
            excesses.append(
                _annualized_return(strategy_period, rule.annualization_days)
                - _annualized_return(fund_period, rule.annualization_days)
            )
        subperiod_medians.append(float(np.median(excesses)))

    basket_median = float(np.median([result.annualized_excess for result in pair_results]))
    positive_funds = sum(result.annualized_excess > 0 for result in pair_results)
    positive_subperiods = sum(value > 0 for value in subperiod_medians)
    passed = (
        basket_median > 0
        and positive_funds >= rule.minimum_positive_funds
        and positive_subperiods >= rule.minimum_positive_subperiods
    )
    return G8Result(
        spec_version=rule.spec_version,
        as_of=verdict_date.date().isoformat(),
        window_start=window_start.date().isoformat(),
        window_end=window_end.date().isoformat(),
        status="PASS" if passed else "TRIGGER_G8",
        basket_median_annualized_excess=basket_median,
        positive_fund_count=positive_funds,
        positive_subperiod_count=positive_subperiods,
        pair_results=tuple(pair_results),
        subperiod_median_excess=tuple(subperiod_medians),
    )


def main() -> int:
    print(json.dumps(frozen_spec(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
