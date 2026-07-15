"""Tushare 基础表采集计划与执行器。所有请求都显式 fields，所有响应都独立入账。"""

import time
from calendar import monthrange
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

import pandas as pd

from shaiwei.config import Settings
from shaiwei.ingest.core import RawBatch, RawBatchWriter


class QueryClient(Protocol):
    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame: ...


class IngestError(RuntimeError):
    pass


FIELDS: dict[str, tuple[str, ...]] = {
    "trade_cal": ("exchange", "cal_date", "is_open", "pretrade_date"),
    "stock_basic": (
        "ts_code", "symbol", "name", "area", "industry", "market", "exchange",
        "list_status", "list_date", "delist_date", "is_hs",
    ),
    "namechange": ("ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"),
    "index_weight": ("index_code", "con_code", "trade_date", "weight"),
    "suspend_d": ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
    "daily": (
        "ts_code", "trade_date", "open", "high", "low", "close", "pre_close",
        "change", "pct_chg", "vol", "amount",
    ),
    "adj_factor": ("ts_code", "trade_date", "adj_factor"),
    "daily_basic": ("ts_code", "trade_date", "close", "turnover_rate", "volume_ratio", "total_mv", "circ_mv"),
    "index_daily": (
        "ts_code", "trade_date", "open", "high", "low", "close", "pre_close",
        "change", "pct_chg", "vol", "amount",
    ),
    "income": (
        "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "end_type",
        "basic_eps", "total_revenue", "revenue", "total_cogs", "operate_profit", "total_profit",
        "n_income", "n_income_attr_p", "ebit", "ebitda", "rd_exp", "update_flag",
    ),
    "balancesheet": (
        "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "end_type",
        "total_share", "money_cap", "accounts_receiv", "inventories", "total_cur_assets", "total_assets",
        "total_cur_liab", "total_liab", "total_hldr_eqy_exc_min_int", "total_hldr_eqy_inc_min_int",
        "update_flag",
    ),
    "cashflow": (
        "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "end_type",
        "net_profit", "n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act", "free_cashflow",
        "n_incr_cash_cash_equ", "c_cash_equ_end_period", "update_flag",
    ),
}


@dataclass(frozen=True)
class Request:
    api_name: str
    params: dict[str, str]
    partitions: dict[str, str]


def month_windows(start: date, end: date) -> Iterable[tuple[date, date]]:
    if start > end:
        raise ValueError("start must not be after end")
    cursor = start.replace(day=1)
    while cursor <= end:
        last = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        yield max(start, cursor), min(end, last)
        cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)


def year_windows(start: date, end: date, years: int) -> Iterable[tuple[date, date]]:
    if start > end:
        raise ValueError("start must not be after end")
    if years < 1:
        raise ValueError("years must be positive")
    cursor = start
    while cursor <= end:
        boundary = date(cursor.year + years, 1, 1)
        window_end = min(end, boundary - timedelta(days=1))
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def _eligible_securities(stock_basic: pd.DataFrame, settings: Settings, as_of: date) -> pd.DataFrame:
    required = {"ts_code", "list_date", "delist_date"}
    if missing := required - set(stock_basic.columns):
        raise ValueError(f"stock_basic missing fields: {sorted(missing)}")
    frame = stock_basic.copy()
    frame["parsed_list_date"] = pd.to_datetime(frame["list_date"], format="%Y%m%d", errors="coerce")
    frame["parsed_delist_date"] = pd.to_datetime(frame["delist_date"], format="%Y%m%d", errors="coerce")
    mask = frame["parsed_list_date"].le(pd.Timestamp(as_of))
    mask &= frame["parsed_delist_date"].isna() | frame["parsed_delist_date"].ge(
        pd.Timestamp(settings.backtest.start)
    )
    if not settings.universe.include_bse:
        mask &= ~frame["ts_code"].astype("string").str.endswith(".BJ", na=False)
    return frame.loc[mask].sort_values("ts_code").drop_duplicates("ts_code", keep="last")


def build_market_plan(settings: Settings, as_of: date, stock_basic: pd.DataFrame) -> list[Request]:
    requests = []
    for security in _eligible_securities(stock_basic, settings, as_of).itertuples(index=False):
        listed = security.parsed_list_date.date()
        start = max(settings.backtest.start, listed)
        end = min(as_of, security.parsed_delist_date.date()) if pd.notna(security.parsed_delist_date) else as_of
        for window_start, window_end in year_windows(start, end, settings.ingest.history_window_years):
            params = {
                "ts_code": security.ts_code,
                "start_date": window_start.strftime("%Y%m%d"),
                "end_date": window_end.strftime("%Y%m%d"),
            }
            partitions = {
                "symbol": security.ts_code,
                "period": f"{window_start:%Y%m%d}-{window_end:%Y%m%d}",
            }
            requests.extend(Request(api, params, partitions) for api in ("daily", "adj_factor", "daily_basic"))
    return requests


def build_financial_plan(settings: Settings, as_of: date, stock_basic: pd.DataFrame) -> list[Request]:
    requests = []
    for security in _eligible_securities(stock_basic, settings, as_of).itertuples(index=False):
        start = max(settings.backtest.start, security.parsed_list_date.date())
        params = {
            "ts_code": security.ts_code,
            "start_date": start.strftime("%Y%m%d"),
            "end_date": as_of.strftime("%Y%m%d"),
        }
        partitions = {"symbol": security.ts_code, "horizon": f"{start:%Y%m%d}-{as_of:%Y%m%d}"}
        requests.extend(Request(api, params, partitions) for api in ("income", "balancesheet", "cashflow"))
    return requests


def build_bootstrap_plan(settings: Settings, as_of: date) -> list[Request]:
    start = settings.backtest.start
    if as_of < start:
        raise ValueError("as_of must be on or after backtest.start")
    requests = [
        Request(
            "trade_cal",
            {"exchange": "SSE", "start_date": start.strftime("%Y%m%d"), "end_date": as_of.strftime("%Y%m%d")},
            {"exchange": "SSE"},
        )
    ]
    requests.append(
        Request(
            "index_daily",
            {
                "ts_code": settings.universe.index_code,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": as_of.strftime("%Y%m%d"),
            },
            {"symbol": settings.universe.index_code},
        )
    )
    requests.extend(
        Request("stock_basic", {"exchange": "", "list_status": status}, {"list_status": status})
        for status in ("L", "D", "P")
    )
    # DATA_SPEC: date parameters here are forbidden because historical rows are silently lost.
    requests.append(Request("namechange", {}, {"scope": "all"}))
    for window_start, window_end in month_windows(start, as_of):
        period = window_start.strftime("%Y-%m")
        date_params = {
            "start_date": window_start.strftime("%Y%m%d"),
            "end_date": window_end.strftime("%Y%m%d"),
        }
        requests.append(
            Request(
                "index_weight",
                {"index_code": settings.universe.index_code, **date_params},
                {"period": period},
            )
        )
        requests.append(Request("suspend_d", date_params, {"period": period}))
    return requests


class TushareIngestor:
    def __init__(
        self,
        *,
        client: QueryClient,
        writer: RawBatchWriter,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.writer = writer
        self.settings = settings
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = self.monotonic() - self._last_request_at
        remaining = self.settings.ingest.min_request_interval_seconds - elapsed
        if remaining > 0:
            self.sleep(remaining)

    def _query(self, request: Request) -> pd.DataFrame:
        if request.api_name == "namechange" and ({"start_date", "end_date"} & request.params.keys()):
            raise IngestError("namechange must be fetched without date filters")
        fields = FIELDS[request.api_name]
        error: Exception | None = None
        for attempt in range(self.settings.ingest.max_attempts):
            self._throttle()
            try:
                frame = self.client.query(request.api_name, fields=",".join(fields), **request.params)
                self._last_request_at = self.monotonic()
                break
            except Exception as exc:
                self._last_request_at = self.monotonic()
                error = exc
                if attempt + 1 < self.settings.ingest.max_attempts:
                    self.sleep(self.settings.ingest.retry_base_seconds * (2**attempt))
        else:
            raise IngestError(
                f"Tushare {request.api_name} failed after {self.settings.ingest.max_attempts} attempts"
            ) from error

        if not isinstance(frame, pd.DataFrame):
            raise IngestError(f"Tushare {request.api_name} returned {type(frame).__name__}, expected DataFrame")
        missing = set(fields) - set(frame.columns)
        if missing:
            raise IngestError(f"Tushare {request.api_name} response missing fields: {sorted(missing)}")
        if len(frame) >= self.settings.ingest.source_row_limit:
            raise IngestError(
                f"Tushare {request.api_name} returned {len(frame)} rows at/above configured limit; "
                "refuse possible truncation"
            )
        return frame.loc[:, fields]

    def run(self, requests: Iterable[Request]) -> list[RawBatch]:
        batches = []
        for request in requests:
            frame = self._query(request)
            public_params = {**request.params, "fields": ",".join(FIELDS[request.api_name])}
            batches.append(
                self.writer.write(
                    source_api=f"tushare.{request.api_name}",
                    params=public_params,
                    frame=frame,
                    partitions=request.partitions,
                )
            )
        return batches


def create_client(token: str) -> QueryClient:
    import tushare as ts

    return ts.pro_api(token)
