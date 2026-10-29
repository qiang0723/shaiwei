"""The single write-once R2-1R1 descriptive report for the latched segment (predecessor §6 formulae)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from shaiwei.research.r2_1r1.contract import Contract, R21R1Error
from shaiwei.research.r2_1r1.segment import AccountDay, Segment, started_local_date


def _money(value: object) -> Decimal:
    return Decimal(str(value))


def _text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001")), "f")


def anchor_date(account_days: Mapping[str, Mapping[str, list[AccountDay]]], first: str) -> str:
    """Last execution date before the segment on which both accounts have exactly one PASS row."""
    common = [
        day for day in account_days["control"]
        if day < first and len(account_days["control"][day]) == 1 and len(account_days["comparison"].get(day, [])) == 1
    ]
    if not common:
        raise R21R1Error("R2-1R1 latched segment has no common anchor state")
    return max(common)


def build_report(
    contract: Contract,
    segment: Segment,
    account_days: Mapping[str, Mapping[str, list[AccountDay]]],
    documents: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """`documents[role][date]` is the verified paper document for each window day and the anchor."""
    if segment.latch_day is None:
        raise R21R1Error("R2-1R1 descriptive report requires a latched segment")
    window = [day for day in segment.days if day <= segment.latch_day]
    anchor = anchor_date(account_days, segment.first)
    per_account: dict[str, Any] = {}
    series: dict[str, dict[str, dict[str, str]]] = {day: {} for day in window}
    for account in contract.accounts:
        anchor_nav = dict(dict(documents[account.role][anchor]["result"])["nav"])
        anchor_row = account_days[account.role][anchor][0].row
        peak, drawdown, turnover, cash_ratios = Decimal("0"), Decimal("0"), Decimal("0"), []
        last_nav: dict[str, Any] = {}
        for day in window:
            nav = dict(dict(documents[account.role][day]["result"])["nav"])
            portfolio = _money(nav["normalized_nav"]) / _money(anchor_nav["normalized_nav"])
            benchmark = _money(nav["benchmark_nav"]) / _money(anchor_nav["benchmark_nav"])
            peak = max(peak, portfolio)
            drawdown = min(drawdown, portfolio / peak - 1)
            turnover += _money(nav["turnover"])
            cash_ratios.append(_money(nav["cash_ratio"]))
            series[day][account.role] = {"portfolio_nav": _text(portfolio), "benchmark_nav": _text(benchmark),
                                         "net_excess": _text(portfolio - benchmark)}
            last_nav = nav
        final = series[window[-1]][account.role]
        per_account[account.role] = {
            "account_id": account.account_id,
            "anchored_portfolio_nav": final["portfolio_nav"],
            "anchored_benchmark_nav": final["benchmark_nav"],
            "anchored_net_excess": final["net_excess"],
            "maximum_drawdown": _text(drawdown),
            "cumulative_turnover": _text(turnover),
            "checkpoint_fees": _text(_money(last_nav["cumulative_fees"]) - _money(anchor_nav["cumulative_fees"])),
            "latest_cash_ratio": _text(cash_ratios[-1]),
            "mean_cash_ratio": _text(sum(cash_ratios, Decimal("0")) / len(cash_ratios)),
            "latest_position_count": len(list(last_nav.get("positions", []))),
            "anchor_stratum": "SAME_DAY" if started_local_date(anchor_row) == anchor else "CONTROLLED_CATCHUP",
        }
    rebalances = []
    for day in segment.rebalances:
        if day > segment.latch_day:
            continue
        entry: dict[str, Any] = {"execution_trade_date": day}
        for account in contract.accounts:
            result = dict(documents[account.role][day]["result"])
            orders = [dict(order) for order in result.get("orders", [])]
            entry[account.role] = {"orders": len(orders), "filled": sum(order.get("status") == "FILLED" for order in orders),
                                   "rejected": sum(order.get("status") == "REJECTED" for order in orders),
                                   "fills": len(list(result.get("fills", [])))}
        rebalances.append(entry)
    paired = [
        {"execution_trade_date": day,
         "top20_minus_top30_anchored_portfolio_nav": _text(_money(values["comparison"]["portfolio_nav"]) - _money(values["control"]["portfolio_nav"])),
         "top20_minus_top30_anchored_net_excess": _text(_money(values["comparison"]["net_excess"]) - _money(values["control"]["net_excess"]))}
        for day, values in series.items()
    ]
    return {
        "schema_version": "r2-1r1-descriptive-report-v1",
        "protocol_sha256": contract.sha256,
        "segment": {"first": segment.first, "latch_day": segment.latch_day, "live_dual_days": len(window),
                    "rebalance_cycles": len(rebalances), "code_snapshot": segment.code_snapshot, "anchor_execution_date": anchor},
        "per_account": per_account,
        "paired_series": paired,
        "rebalance_comparison": rebalances,
        "series": [{"execution_trade_date": day, **values} for day, values in series.items()],
        "not_a_strategy_verdict": True,
        "prohibited_outputs": list(contract.document["prohibited_outputs"]),
        "production_authorization": "none",
    }


def write_once(path: Path, document: Mapping[str, Any]) -> str:
    payload = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise R21R1Error("R2-1R1 descriptive report already exists; it is generated exactly once") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
    return hashlib.sha256(payload).hexdigest()


def generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()
