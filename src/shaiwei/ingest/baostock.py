"""Baostock 独立交易状态采集，仅覆盖 S1/S6 的歧义日期。"""

import argparse
import json
from datetime import date
from typing import Any

import pandas as pd

from shaiwei.ingest.core import RawBatch, RawBatchWriter
from shaiwei.transform.availability import StatusWindow, build_status_crosscheck_plan

SOURCE_API = "baostock.history_k_data_plus"
FIELDS = "date,code,tradestatus"


def baostock_code(ts_code: str) -> str:
    symbol, exchange = ts_code.split(".", maxsplit=1)
    prefixes = {"SH": "sh", "SZ": "sz"}
    if exchange not in prefixes:
        raise ValueError(f"Baostock does not support exchange: {exchange}")
    return f"{prefixes[exchange]}.{symbol}"


def request_params(request: StatusWindow) -> dict[str, str]:
    return {
        "code": baostock_code(request.ts_code),
        "fields": FIELDS,
        "start_date": f"{request.start_date[:4]}-{request.start_date[4:6]}-{request.start_date[6:]}",
        "end_date": f"{request.end_date[:4]}-{request.end_date[4:6]}-{request.end_date[6:]}",
        "frequency": "d",
        "adjustflag": "3",
    }


def _require_success(result: Any, operation: str) -> None:
    if str(result.error_code) != "0":
        raise RuntimeError(f"Baostock {operation} failed: {result.error_code} {result.error_msg}")


class BaostockStatusIngestor:
    def __init__(self, writer: RawBatchWriter, client: Any | None = None) -> None:
        if client is None:
            import baostock as bs

            client = bs
        self.writer = writer
        self.client = client

    def _fetch(self, request: StatusWindow) -> pd.DataFrame:
        params = request_params(request)
        result = self.client.query_history_k_data_plus(**params)
        _require_success(result, "query_history_k_data_plus")
        rows = []
        while result.next():
            rows.append(result.get_row_data())
        frame = pd.DataFrame(rows, columns=result.fields)
        if missing := set(FIELDS.split(",")) - set(frame.columns):
            raise ValueError(f"Baostock response missing fields: {sorted(missing)}")
        if frame.empty:
            raise ValueError(f"Baostock returned no status rows for {request.ts_code}")
        frame = frame.rename(columns={"date": "trade_date", "tradestatus": "trade_status"})
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="raise").dt.strftime("%Y%m%d")
        expected_code = baostock_code(request.ts_code)
        if set(frame["code"].astype(str)) != {expected_code}:
            raise ValueError(f"Baostock code mismatch for {request.ts_code}")
        frame["trade_status"] = frame["trade_status"].astype(str).str.strip()
        if not set(frame["trade_status"]).issubset({"0", "1"}):
            raise ValueError(f"Baostock returned invalid trade status for {request.ts_code}")
        if frame["trade_date"].duplicated().any():
            raise ValueError(f"Baostock returned duplicate dates for {request.ts_code}")
        required = set(request.required_dates)
        observed = set(frame["trade_date"])
        if missing_dates := required - observed:
            raise ValueError(
                f"Baostock omitted {len(missing_dates)} required dates for {request.ts_code}: "
                f"{sorted(missing_dates)[:5]}"
            )
        frame = frame.loc[frame["trade_date"].isin(required), ["trade_date", "trade_status"]].copy()
        frame.insert(0, "ts_code", request.ts_code)
        return frame.sort_values("trade_date").reset_index(drop=True)

    def run(self, requests: list[StatusWindow]) -> list[RawBatch]:
        login = self.client.login()
        _require_success(login, "login")
        batches = []
        try:
            for request in requests:
                frame = self._fetch(request)
                batches.append(
                    self.writer.write(
                        source_api=SOURCE_API,
                        params=request_params(request),
                        frame=frame,
                        partitions={
                            "symbol": request.ts_code,
                            "period": f"{request.start_date}-{request.end_date}",
                        },
                    )
                )
        finally:
            logout = self.client.logout()
            _require_success(logout, "logout")
        return batches


def main() -> int:
    from shaiwei.config import load
    from shaiwei.ingest.catalog import canonical_params_key, committed_params_keys, load_latest_api

    parser = argparse.ArgumentParser(description="筛微 S1/S6 独立交易状态采集")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    settings = load()
    daily = load_latest_api("tushare.daily")
    end = min(args.as_of.strftime("%Y%m%d"), max(daily["trade_date"].astype(str)))
    plan = build_status_crosscheck_plan(
        load_latest_api("tushare.trade_cal"),
        load_latest_api("tushare.stock_basic"),
        daily,
        load_latest_api("tushare.suspend_d"),
        start=settings.backtest.start.strftime("%Y%m%d"),
        end=end,
        include_bse=settings.universe.include_bse,
    )
    planned_count = len(plan)
    planned_dates = sum(len(request.required_dates) for request in plan)
    if args.resume:
        committed = committed_params_keys(SOURCE_API)
        plan = [
            request for request in plan
            if canonical_params_key(request_params(request)) not in committed
        ]
    summary = {
        "as_of": args.as_of.isoformat(),
        "planned_request_count": planned_count,
        "planned_status_date_count": planned_dates,
        "request_count": len(plan),
        "skipped_committed_count": planned_count - len(plan),
    }
    if args.dry_run or not plan:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    batches = BaostockStatusIngestor(RawBatchWriter(settings.runtime.data_root)).run(plan)
    print(json.dumps({
        **summary,
        "batch_count": len(batches),
        "row_count": sum(batch.row_count for batch in batches),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
