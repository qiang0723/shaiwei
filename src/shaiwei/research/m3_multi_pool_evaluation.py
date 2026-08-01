"""Pure three-pool discovery scoring and deterministic M3-1 synthetic fixtures."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import torch

from shaiwei.benchmark.fitness import neutralized_rank_ic
from shaiwei.research.alphagen_expression import ExpressionAudit, audit_expression, parse_safe_expression
from shaiwei.research.candidate_semantics import validate_candidate_semantics
from shaiwei.research.llm_factor import CandidateProposal, D1ControlError
from shaiwei.research.m3_multi_pool_contract import M3Protocol, POOL_IDS


_POOL_VARIATION = re.compile(
    r"(?:全市场|中盘|小盘).{0,24}(?:改用|分别|单独|不同|相反|翻转|正向|负向)|"
    r"分别(?:采用|使用|设置).{0,24}(?:公式|方向|窗口|参数)"
)


def validate_m3_candidate_semantics(proposal: CandidateProposal) -> str | None:
    generic = validate_candidate_semantics(proposal)
    if generic is not None:
        return generic
    narrative = "\n".join(
        (proposal.hypothesis, proposal.economic_rationale_draft, *proposal.known_failure_risks)
    )
    if _POOL_VARIATION.search(narrative):
        return "pool_specific_formula_or_direction"
    return None


@dataclass(frozen=True)
class PoolEvidence:
    universe_id: str
    eligible_rows: int
    covered_rows: int
    coverage: float
    daily_ic_count: int
    rank_ic: float | None
    structural_pass: bool
    failures: tuple[str, ...]


@dataclass(frozen=True)
class CrossPoolEvidence:
    candidate_id: str
    normalized_expression: str
    audit: ExpressionAudit
    pool_evidence: dict[str, PoolEvidence]
    direction: int | None
    directed_rank_ic: dict[str, float]
    cross_pool_score: float | None
    secondary_score: float | None
    minimum_coverage: float
    eligible: bool
    failures: tuple[str, ...]
    global_ordinal: int


def _finite(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in columns:
        mask &= np.isfinite(pd.to_numeric(frame[column], errors="coerce"))
    return mask


def evaluate_pool(
    frame: pd.DataFrame,
    *,
    universe_id: str,
    minimum_cross_section: int,
    minimum_coverage: float,
    minimum_daily_ic: int,
) -> PoolEvidence:
    required = {"trade_date", "instrument", "factor", "label", "industry", "market_cap"}
    if missing := required - set(frame.columns):
        raise D1ControlError(f"M3-1 pool observations are missing: {sorted(missing)}")
    if frame.duplicated(["trade_date", "instrument"]).any():
        raise D1ControlError("M3-1 pool observations contain duplicate member days")
    if frame["instrument"].astype(str).str.upper().str.endswith(".BJ").any():
        raise D1ControlError("M3-1 pool observations contain forbidden .BJ")
    denominator = _finite(frame, ("label", "market_cap"))
    denominator &= frame["market_cap"].gt(0) & frame["industry"].notna()
    numerator = denominator & _finite(frame, ("factor",))
    eligible_rows = int(denominator.sum())
    covered_rows = int(numerator.sum())
    coverage = covered_rows / eligible_rows if eligible_rows else 0.0
    rank_ic, daily_ic = neutralized_rank_ic(frame.loc[denominator].copy(), minimum_cross_section)
    finite_rank_ic = float(rank_ic) if math.isfinite(float(rank_ic)) else None
    failures: list[str] = []
    if coverage < minimum_coverage:
        failures.append("coverage_below_minimum")
    if len(daily_ic) < minimum_daily_ic or finite_rank_ic is None:
        failures.append(f"insufficient_daily_ic:{len(daily_ic)}")
    return PoolEvidence(
        universe_id=universe_id,
        eligible_rows=eligible_rows,
        covered_rows=covered_rows,
        coverage=coverage,
        daily_ic_count=len(daily_ic),
        rank_ic=finite_rank_ic,
        structural_pass=not failures,
        failures=tuple(failures),
    )


def evaluate_cross_pool_candidate(
    expression: str,
    frames: dict[str, pd.DataFrame],
    protocol: M3Protocol,
    *,
    global_ordinal: int,
) -> CrossPoolEvidence:
    if set(frames) != set(POOL_IDS.values()):
        raise D1ControlError("M3-1 candidate must have exactly three frozen pool cells")
    audit = audit_expression(expression)
    candidate = protocol.document["candidate_contract"]
    if (
        audit.expression_tokens > int(candidate["maximum_expression_tokens"])
        or audit.ast_nodes > int(candidate["maximum_ast_nodes"])
        or audit.max_lookback_days > int(candidate["maximum_lookback_trade_days"])
        or not audit.pit_sentinel_pass
        or not audit.shift_sentinel_pass
    ):
        raise D1ControlError("M3-1 candidate failed DSL complexity or PIT/shift gates")
    discovery = protocol.document["discovery_evaluation"]
    universes = protocol.document["universes"]
    evidence: dict[str, PoolEvidence] = {}
    for name, pool_id in POOL_IDS.items():
        evidence[pool_id] = evaluate_pool(
            frames[pool_id],
            universe_id=pool_id,
            minimum_cross_section=int(universes[name]["minimum_cross_section"]),
            minimum_coverage=float(discovery["minimum_candidate_coverage_each_pool"]),
            minimum_daily_ic=int(discovery["minimum_daily_ic_observations_each_pool"]),
        )
    anchor = evidence[POOL_IDS["all"]]
    direction = None
    failures: list[str] = []
    if anchor.rank_ic is None or anchor.rank_ic == 0:
        failures.append("anchor_rank_ic_zero_or_nonfinite")
    else:
        direction = 1 if anchor.rank_ic > 0 else -1
    directed: dict[str, float] = {}
    for pool_id, pool in evidence.items():
        if not pool.structural_pass:
            failures.extend(f"{pool_id}:{reason}" for reason in pool.failures)
        if direction is not None and pool.rank_ic is not None:
            directed[pool_id] = direction * pool.rank_ic
            if directed[pool_id] <= 0:
                failures.append(f"{pool_id}:directed_rank_ic_not_positive")
    complete = len(directed) == len(POOL_IDS)
    values = list(directed.values())
    score = min(values) if complete else None
    secondary = float(np.median(values)) if complete else None
    normalized = audit.normalized_expression
    candidate_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return CrossPoolEvidence(
        candidate_id=candidate_id,
        normalized_expression=normalized,
        audit=audit,
        pool_evidence=evidence,
        direction=direction,
        directed_rank_ic=directed,
        cross_pool_score=score,
        secondary_score=secondary,
        minimum_coverage=min(pool.coverage for pool in evidence.values()),
        eligible=not failures and complete,
        failures=tuple(failures),
        global_ordinal=global_ordinal,
    )


def rank_candidates(
    candidates: list[CrossPoolEvidence],
    *,
    promoted_count: int,
) -> list[CrossPoolEvidence]:
    eligible = [candidate for candidate in candidates if candidate.eligible]
    eligible.sort(
        key=lambda candidate: (
            -float(candidate.cross_pool_score),
            -float(candidate.secondary_score),
            -candidate.minimum_coverage,
            candidate.audit.expression_tokens,
            candidate.global_ordinal,
        )
    )
    return eligible[:promoted_count]


class _SyntheticStockData:
    def __init__(self, data: torch.Tensor, *, backtrack: int, future: int, days: int):
        self.data = data
        self.max_backtrack_days = backtrack
        self.max_future_days = future
        self.n_days = days
        self.n_stocks = data.shape[-1]


def synthetic_three_pool_frames(expression: str, *, days: int = 474) -> dict[str, pd.DataFrame]:
    """Evaluate one real DSL expression on a deterministic, wholly synthetic panel."""
    backtrack, future, stocks = 60, 11, 60
    rows = backtrack + days + future
    time = torch.arange(rows, dtype=torch.float64).reshape(-1, 1)
    drift = torch.linspace(-0.0008, 0.0012, stocks, dtype=torch.float64).reshape(1, -1)
    open_price = 100.0 * torch.exp(time * drift)
    close = open_price * (1.0 + 0.0005 * torch.sin(time / 7.0))
    high = torch.maximum(open_price, close) * 1.01
    low = torch.minimum(open_price, close) * 0.99
    volume = 1_000_000.0 * (1.1 + torch.linspace(0, 0.4, stocks).reshape(1, -1))
    volume = volume.repeat(rows, 1)
    vwap = (open_price + close + high + low) / 4.0
    data = torch.stack((open_price, close, high, low, volume, vwap), dim=1)
    stock_data = _SyntheticStockData(data, backtrack=backtrack, future=future, days=days)
    factor = parse_safe_expression(expression).evaluate(stock_data).detach().cpu().numpy()
    if factor.shape != (days, stocks):
        raise D1ControlError("M3-1 synthetic DSL output shape differs")
    open_values = open_price.detach().cpu().numpy()
    labels = np.vstack(
        [
            open_values[backtrack + index + future]
            / open_values[backtrack + index + 1]
            - 1.0
            for index in range(days)
        ]
    )
    dates = pd.bdate_range("2021-01-04", periods=days)
    instruments = [f"SYN{index:03d}.SH" for index in range(stocks)]
    frames: dict[str, pd.DataFrame] = {}
    selections = {
        POOL_IDS["all"]: range(0, 60),
        POOL_IDS["midcap"]: range(20, 40),
        POOL_IDS["smallcap"]: range(40, 60),
    }
    for pool_id, selected in selections.items():
        records: list[dict[str, Any]] = []
        for day_index, trade_date in enumerate(dates):
            for stock_index in selected:
                records.append(
                    {
                        "trade_date": trade_date,
                        "instrument": instruments[stock_index],
                        "factor": float(factor[day_index, stock_index]),
                        "label": float(labels[day_index, stock_index]),
                        "industry": f"I{stock_index % 5}",
                        "market_cap": float(1_000_000_000 * (1 + ((stock_index * 7) % 17) / 20)),
                    }
                )
        frames[pool_id] = pd.DataFrame.from_records(records)
    return frames
