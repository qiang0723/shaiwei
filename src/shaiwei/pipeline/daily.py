"""Docker-native, ledger-driven daily market-data reconciliation."""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import pandas as pd

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ingest.catalog import CatalogError, load_latest_api, load_latest_request
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import (
    Request,
    TushareIngestor,
    create_client,
    public_request_params,
)
from shaiwei.ledger import DAILY_RUNS, INGEST, append_daily_run, ingest_snapshot_sha256
from shaiwei.notify.feishu import FeishuNotifier

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATE_FORMAT = "%Y%m%d"
REQUIRED_BOOTSTRAP_APIS = (
    "tushare.daily",
    "tushare.adj_factor",
    "tushare.daily_basic",
    "tushare.index_daily",
)


class DailyPipelineError(RuntimeError):
    pass


class AlreadyRunning(DailyPipelineError):
    pass


@dataclass(frozen=True)
class DailyPlan:
    now: str
    watermark: str
    eligible_target: str
    missing_trade_dates: tuple[str, ...]


@dataclass(frozen=True)
class DailyResult:
    status: str
    watermark_before: str
    eligible_target: str
    completed_trade_dates: tuple[str, ...]
    batch_count: int
    row_count: int


def _parse_params(value: str) -> dict[str, object]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise DailyPipelineError("ingest ledger params_json must be an object")
    return parsed


def bootstrap_watermark(ledger_path: Path = INGEST) -> str:
    """Recover the frozen historical endpoint from range-based bootstrap rows."""
    maxima: dict[str, str] = {}
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            api = row["source_api"]
            if api not in REQUIRED_BOOTSTRAP_APIS:
                continue
            params = _parse_params(row["params_json"])
            # Daily increments use trade_date.  Ignoring them here prevents a
            # partially written future date from advancing the bootstrap mark.
            end_date = str(params.get("end_date", ""))
            if len(end_date) == 8 and end_date.isdigit():
                maxima[api] = max(maxima.get(api, ""), end_date)
    missing = set(REQUIRED_BOOTSTRAP_APIS) - set(maxima)
    if missing:
        raise DailyPipelineError(f"bootstrap coverage missing APIs: {sorted(missing)}")
    return min(maxima.values())


def passed_trade_dates(path: Path = DAILY_RUNS) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["target_trade_date"]
            for row in csv.DictReader(handle)
            if row.get("status") == "PASS"
        }


def current_watermark(
    *,
    ingest_ledger_path: Path = INGEST,
    daily_ledger_path: Path = DAILY_RUNS,
) -> str:
    completed = passed_trade_dates(daily_ledger_path)
    return max({bootstrap_watermark(ingest_ledger_path), *completed})


def eligible_target_date(now: datetime, settings: Settings) -> date:
    local = now.astimezone(SHANGHAI)
    cutoff = time(settings.daily.ready_hour, settings.daily.ready_minute)
    return local.date() if local.time().replace(tzinfo=None) >= cutoff else local.date() - timedelta(days=1)


def build_plan(
    *,
    now: datetime,
    settings: Settings,
    trade_cal: pd.DataFrame,
    ingest_ledger_path: Path = INGEST,
    daily_ledger_path: Path = DAILY_RUNS,
) -> DailyPlan:
    required = {"cal_date", "is_open"}
    if missing := required - set(trade_cal.columns):
        raise DailyPipelineError(f"trade_cal missing columns: {sorted(missing)}")
    bootstrap = bootstrap_watermark(ingest_ledger_path)
    target = eligible_target_date(now, settings).strftime(DATE_FORMAT)
    completed = passed_trade_dates(daily_ledger_path)
    relevant_open_dates = sorted(
        value
        for value in trade_cal.loc[
            trade_cal["is_open"].astype(str).eq("1"), "cal_date"
        ].astype(str).unique()
        if bootstrap < value <= target
    )
    # Never let an out-of-order PASS hide an earlier hole.  Normal execution
    # is sequential, but this invariant also protects manual ledger recovery.
    watermark = bootstrap
    for trade_date in relevant_open_dates:
        if trade_date not in completed:
            break
        watermark = trade_date
    missing_dates = tuple(
        value for value in relevant_open_dates if value not in completed
    )[: settings.daily.max_catchup_trade_days]
    return DailyPlan(
        now=now.astimezone(SHANGHAI).isoformat(timespec="seconds"),
        watermark=watermark,
        eligible_target=target,
        missing_trade_dates=missing_dates,
    )


def build_market_requests(settings: Settings, trade_date: str) -> list[Request]:
    day_partition = {"trade_date": trade_date}
    requests = [
        Request(api, {"trade_date": trade_date}, day_partition)
        for api in ("daily", "adj_factor", "daily_basic", "suspend_d")
    ]
    requests.append(
        Request(
            "index_daily",
            {"ts_code": settings.universe.index_code, "trade_date": trade_date},
            {"symbol": settings.universe.index_code, "trade_date": trade_date},
        )
    )
    return requests


def build_reference_requests() -> list[Request]:
    return [
        Request("stock_basic", {"exchange": "", "list_status": status}, {"list_status": status})
        for status in ("L", "D", "P")
    ]


def _request_is_committed(request: Request, ledger_path: Path = INGEST) -> bool:
    try:
        load_latest_request(
            f"tushare.{request.api_name}",
            public_request_params(request),
            ledger_path=ledger_path,
        )
    except CatalogError:
        return False
    return True


def _request_frame(request: Request, ledger_path: Path = INGEST) -> pd.DataFrame:
    return load_latest_request(
        f"tushare.{request.api_name}",
        public_request_params(request),
        ledger_path=ledger_path,
    )


def validate_trade_date(
    *,
    settings: Settings,
    trade_date: str,
    request_frames: dict[str, pd.DataFrame],
) -> int:
    dense = ("daily", "adj_factor", "daily_basic", "index_daily")
    for api in dense:
        frame = request_frames[api]
        if frame.empty:
            raise DailyPipelineError(f"{api} is empty for open date {trade_date}")
        dates = set(frame["trade_date"].dropna().astype(str).unique())
        if dates != {trade_date}:
            raise DailyPipelineError(f"{api} returned wrong dates: {sorted(dates)}")
        if frame.duplicated(["ts_code", "trade_date"]).any():
            raise DailyPipelineError(f"{api} contains duplicate security-date keys")
    for api, frame in request_frames.items():
        if "ts_code" in frame and frame["ts_code"].astype("string").str.endswith(".BJ", na=False).any():
            raise DailyPipelineError(f"{api} contains forbidden BSE rows")

    daily_codes = set(request_frames["daily"]["ts_code"].astype(str))
    factor_codes = set(request_frames["adj_factor"]["ts_code"].astype(str))
    basic_codes = set(request_frames["daily_basic"]["ts_code"].astype(str))
    if len(daily_codes) < settings.daily.min_market_rows:
        raise DailyPipelineError(
            f"daily market breadth {len(daily_codes)} below {settings.daily.min_market_rows}"
        )
    # Adjustment/valuation snapshots can legitimately include a suspended
    # security for which no OHLCV row exists.  Every traded security must be
    # covered, while harmless snapshot extras are allowed.
    if not daily_codes <= factor_codes:
        raise DailyPipelineError("adj_factor is missing traded securities")
    if not daily_codes <= basic_codes:
        raise DailyPipelineError("daily_basic is missing traded securities")
    index = request_frames["index_daily"]
    if set(index["ts_code"].astype(str)) != {settings.universe.index_code}:
        raise DailyPipelineError("index_daily benchmark row is missing or unexpected")
    return sum(len(frame) for frame in request_frames.values())


def _next_month_end(day: date) -> date:
    first_next = (day.replace(day=1) + timedelta(days=32)).replace(day=1)
    first_after_next = (first_next + timedelta(days=32)).replace(day=1)
    return first_after_next - timedelta(days=1)


def refresh_trade_calendar(
    *,
    settings: Settings,
    now: datetime,
    client: object,
    writer: RawBatchWriter,
) -> pd.DataFrame:
    calendar = load_latest_api("tushare.trade_cal")
    maximum = max(calendar["cal_date"].astype(str))
    desired = _next_month_end(now.astimezone(SHANGHAI).date()).strftime(DATE_FORMAT)
    if maximum >= desired:
        return calendar
    start = (datetime.strptime(maximum, DATE_FORMAT).date() + timedelta(days=1)).strftime(DATE_FORMAT)
    request = Request(
        "trade_cal",
        {"exchange": "SSE", "start_date": start, "end_date": desired},
        {"exchange": "SSE", "period": f"{start}-{desired}"},
    )
    if not _request_is_committed(request):
        TushareIngestor(client=client, writer=writer, settings=settings).run([request])
    return load_latest_api("tushare.trade_cal")


@contextmanager
def daily_lock(path: Path | None = None) -> Iterator[None]:
    lock_path = path or PROJECT_ROOT / "logs" / "scheduler" / "daily.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AlreadyRunning("another daily reconciliation is already running") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _notify(notifier: FeishuNotifier, event: str, title: str, fields: dict[str, object]) -> None:
    notifier.send(event, title, fields)


def _execute_date(
    *,
    settings: Settings,
    trade_date: str,
    client: object,
    writer: RawBatchWriter,
    notifier: FeishuNotifier,
) -> tuple[int, int]:
    started_at = datetime.now(timezone.utc).isoformat()
    batch_count = 0
    try:
        requests = build_market_requests(settings, trade_date)
        pending = [request for request in requests if not _request_is_committed(request)]
        if pending:
            batch_count += len(
                TushareIngestor(client=client, writer=writer, settings=settings).run(pending)
            )
        frames = {request.api_name: _request_frame(request) for request in requests}
        row_count = validate_trade_date(
            settings=settings,
            trade_date=trade_date,
            request_frames=frames,
        )
        snapshot = ingest_snapshot_sha256()
        append_daily_run(
            started_at=started_at,
            target_trade_date=trade_date,
            status="PASS",
            batch_count=batch_count,
            row_count=row_count,
            data_snapshot_sha256=snapshot,
            error_type="",
        )
        return batch_count, row_count
    except Exception as error:
        append_daily_run(
            started_at=started_at,
            target_trade_date=trade_date,
            status="FAIL",
            batch_count=batch_count,
            row_count=0,
            data_snapshot_sha256="",
            error_type=type(error).__name__,
        )
        _notify(
            notifier,
            "daily_increment_failed",
            "日增量采集失败",
            {"trade_date": trade_date, "error_type": type(error).__name__},
        )
        raise


def run_once(*, settings: Settings | None = None, now: datetime | None = None) -> DailyResult:
    settings = settings or load()
    now = now or datetime.now(timezone.utc)
    token = settings.runtime.tushare_token
    if token is None:
        raise DailyPipelineError("TUSHARE_TOKEN is required")
    notifier = FeishuNotifier(settings.notifications)
    client = create_client(token.get_secret_value())
    writer = RawBatchWriter(settings.runtime.data_root)
    with daily_lock():
        calendar = refresh_trade_calendar(settings=settings, now=now, client=client, writer=writer)
        plan = build_plan(now=now, settings=settings, trade_cal=calendar)
        if not plan.missing_trade_dates:
            return DailyResult("NOOP", plan.watermark, plan.eligible_target, (), 0, 0)
        _notify(
            notifier,
            "daily_catchup_started",
            "日增量补采开始",
            {
                "watermark": plan.watermark,
                "target": plan.eligible_target,
                "trade_days": len(plan.missing_trade_dates),
            },
        )
        # One current reference snapshot is sufficient for the whole catch-up
        # window.  It is intentionally refreshed even though the API params
        # match an older snapshot, so new listings are visible immediately.
        reference_batches = TushareIngestor(
            client=client, writer=writer, settings=settings
        ).run(build_reference_requests())
        completed: list[str] = []
        batch_count = len(reference_batches)
        row_count = 0
        for trade_date in plan.missing_trade_dates:
            batches, rows = _execute_date(
                settings=settings,
                trade_date=trade_date,
                client=client,
                writer=writer,
                notifier=notifier,
            )
            completed.append(trade_date)
            batch_count += batches
            row_count += rows
        _notify(
            notifier,
            "daily_catchup_passed",
            "日增量补采完成",
            {
                "from": completed[0],
                "to": completed[-1],
                "trade_days": len(completed),
                "rows": row_count,
            },
        )
        return DailyResult(
            "PASS",
            plan.watermark,
            plan.eligible_target,
            tuple(completed),
            batch_count,
            row_count,
        )


def _local_plan(settings: Settings, now: datetime) -> DailyPlan:
    return build_plan(
        now=now,
        settings=settings,
        trade_cal=load_latest_api("tushare.trade_cal"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="show a read-only local reconciliation plan")
    args = parser.parse_args(argv)
    settings = load()
    now = datetime.now(timezone.utc)
    if args.plan:
        print(json.dumps(asdict(_local_plan(settings, now)), ensure_ascii=False, sort_keys=True))
        return 0
    result = run_once(settings=settings, now=now)
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
