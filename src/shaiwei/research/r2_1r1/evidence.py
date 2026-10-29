"""Read-only R2-1R1 evidence loading: SSE calendar, verified paper documents, journal replay and shadow signals."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from shaiwei.ledger import INGEST, SHADOW_RUNS, resolve_artifact_path, sha256_file
from shaiwei.research.r2_1r1.contract import Contract, R21R1Error
from shaiwei.research.r2_1r1.segment import AccountDay, DayEvidence, Signal, classify_day
from shaiwei.research.trend_swing.sources import latest_source_entries


def _day(value: str) -> date:
    return date(int(value[:4]), int(value[4:6]), int(value[6:]))


def official_open_days(start: str, end: str, *, ingest_path: Path = INGEST) -> list[str]:
    """SSE open days from the latest trade_cal batch per params key; every calendar day in range must be covered."""
    ledger = pd.read_csv(ingest_path, dtype=str, keep_default_na=False)
    entries = latest_source_entries(ledger, "tushare.trade_cal")
    status: dict[str, str] = {}
    for entry in entries.itertuples(index=False):
        path = resolve_artifact_path(entry.parquet_path)
        if not path.is_file() or sha256_file(path) != entry.content_sha256:
            raise R21R1Error(f"R2-1R1 trade calendar batch differs from the ingest ledger: {entry.batch_id}")
        frame = pd.read_parquet(path, columns=["exchange", "cal_date", "is_open"])
        for exchange, cal_date, is_open in frame.astype(str).itertuples(index=False, name=None):
            if exchange != "SSE":
                continue
            flag = "1" if is_open in {"1", "1.0"} else "0"
            if status.setdefault(cal_date, flag) != flag:
                raise R21R1Error(f"R2-1R1 trade calendar batches conflict on {cal_date}")
    cursor, last = _day(start), _day(end)
    while cursor <= last:
        if cursor.strftime("%Y%m%d") not in status:
            raise R21R1Error(f"R2-1R1 trade calendar does not cover {cursor:%Y%m%d}")
        cursor += timedelta(days=1)
    return sorted(day for day, flag in status.items() if start <= day <= end and flag == "1")


def next_official_open_day(after: str, *, ingest_path: Path = INGEST) -> str | None:
    try:
        days = official_open_days(after, (_day(after) + timedelta(days=14)).strftime("%Y%m%d"), ingest_path=ingest_path)
    except R21R1Error:
        return None
    return next((day for day in days if day > after), None)


def daily_gate(document: Mapping[str, Any]) -> bool:
    """Accounting identity, freshness and BSE-free holdings (same predicate as the predecessor evaluator)."""
    nav = dict(dict(document.get("result", {})).get("nav", {}))
    positions = [dict(value) for value in list(nav.get("positions", []))]
    cash, market, net = (Decimal(str(nav.get(name, "0"))) for name in ("cash", "market_value", "net_asset"))
    position_market = sum((Decimal(str(value.get("market_value", "0"))) for value in positions), Decimal("0"))
    return (
        net > 0
        and cash + market == net
        and position_market == market
        and nav.get("freshness_status") == "PASS"
        and not any(str(value.get("ts_code", "")).endswith(".BJ") for value in positions)
    )


def load_account_days(contract: Contract, *, start: str, end: str) -> dict[str, dict[str, list[AccountDay]]]:
    """Every PASS row in range, its artifact re-verified; the whole append-only journal must replay PASS."""
    from shaiwei.paper.query import PaperQueryError, _document, _execution_policy_version, _passed_runs, verify_paper_replay

    result: dict[str, dict[str, list[AccountDay]]] = {}
    for account in contract.accounts:
        try:
            if verify_paper_replay(account.account_id).get("status") != "PASS":
                raise R21R1Error(f"R2-1R1 {account.account_id} journal replay is not PASS")
            by_date: dict[str, list[AccountDay]] = {}
            for row in _passed_runs(account.account_id):
                if not start <= row["execution_trade_date"] <= end:
                    continue
                _, document = _document(row)
                by_date.setdefault(row["execution_trade_date"], []).append(
                    AccountDay(row, str(document.get("mode", "")), _execution_policy_version(document), daily_gate(document))
                )
        except PaperQueryError as exc:
            raise R21R1Error(f"R2-1R1 {account.account_id} paper evidence failed verification: {exc}") from exc
        result[account.role] = by_date
    return result


def load_signals(signal_hashes: set[str], *, path: Path = SHADOW_RUNS) -> dict[str, Signal]:
    from shaiwei.shadow.manifest import verify_signal_manifest

    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["status"] == "PASS" and row["signal_sha256"] in signal_hashes]
    signals: dict[str, Signal] = {}
    for row in rows:
        try:
            actual = verify_signal_manifest(resolve_artifact_path(row["signal_manifest_path"]))
        except (OSError, ValueError, KeyError) as exc:
            raise R21R1Error(f"R2-1R1 shadow signal manifest failed verification: {row['run_id']}") from exc
        if actual != row["signal_sha256"] or row["rebalance_due"] not in {"true", "false"}:
            raise R21R1Error(f"R2-1R1 shadow signal identity differs from its ledger row: {row['run_id']}")
        signal = Signal(row["rebalance_due"] == "true", row["on_time"] == "true")
        if signals.setdefault(row["signal_sha256"], signal) != signal:
            raise R21R1Error("R2-1R1 one signal hash carries conflicting shadow rows")
    return signals


def classify_history(
    contract: Contract,
    *,
    as_of: str,
    calendar: Callable[[str, str], list[str]] = official_open_days,
    accounts: Callable[..., dict[str, dict[str, list[AccountDay]]]] = load_account_days,
    signals: Callable[[set[str]], dict[str, Signal]] = load_signals,
) -> list[DayEvidence]:
    open_days = calendar(contract.history_start, as_of)
    account_days = accounts(contract, start=contract.history_start, end=as_of)
    hashes = {day.row["signal_sha256"] for by_date in account_days.values() for rows in by_date.values() for day in rows}
    lookup = signals(hashes)
    extra = sorted({date for by_date in account_days.values() for date in by_date} - set(open_days))
    if extra:
        raise R21R1Error(f"R2-1R1 paper rows on non-open days: {extra}")
    return [
        classify_day(day, contract, {role: account_days[role].get(day, []) for role in account_days}, lookup)
        for day in open_days
    ]
