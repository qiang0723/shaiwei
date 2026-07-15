"""AKShare 独立源采集适配器，用于 S8 交叉比对。"""

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from shaiwei.ingest.core import RawBatch, RawBatchWriter
from shaiwei.ingest.tushare import _add_no_proxy_host

EASTMONEY_API_HOST = "push2his.eastmoney.com"

AK_COLUMNS = {
    "日期": "trade_date",
    "股票代码": "symbol",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "vol",
    "成交额": "amount",
}


@dataclass(frozen=True)
class CrosscheckRequest:
    ts_code: str
    start: date
    end: date


def request_params(request: CrosscheckRequest) -> dict[str, str]:
    return {
        "symbol": request.ts_code.split(".", maxsplit=1)[0],
        "period": "daily",
        "start_date": request.start.strftime("%Y%m%d"),
        "end_date": request.end.strftime("%Y%m%d"),
        "adjust": "",
    }


class AKShareIngestor:
    def __init__(
        self,
        writer: RawBatchWriter,
        fetch: Callable[..., pd.DataFrame] | None = None,
        *,
        max_attempts: int = 6,
        retry_base_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if fetch is None:
            import akshare as ak

            fetch = ak.stock_zh_a_hist
        self.writer = writer
        self.fetch = fetch
        self.max_attempts = max_attempts
        self.retry_base_seconds = retry_base_seconds
        self.sleep = sleep

    def _fetch_with_retry(self, params: dict[str, str]) -> pd.DataFrame:
        error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                return self.fetch(**params)
            except Exception as exc:
                error = exc
                if attempt + 1 < self.max_attempts:
                    self.sleep(self.retry_base_seconds * (2**attempt))
        raise RuntimeError(f"AKShare request failed after {self.max_attempts} attempts") from error

    def run(self, requests: list[CrosscheckRequest]) -> list[RawBatch]:
        batches = []
        for request in requests:
            params = request_params(request)
            raw = self._fetch_with_retry(params)
            if not isinstance(raw, pd.DataFrame):
                raise TypeError("AKShare stock_zh_a_hist must return DataFrame")
            if missing := set(AK_COLUMNS) - set(raw.columns):
                raise ValueError(f"AKShare response missing fields: {sorted(missing)}")
            frame = raw.loc[:, list(AK_COLUMNS)].rename(columns=AK_COLUMNS).copy()
            frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="raise").dt.strftime("%Y%m%d")
            frame["ts_code"] = request.ts_code
            batches.append(
                self.writer.write(
                    source_api="akshare.stock_zh_a_hist",
                    params=params,
                    frame=frame,
                    partitions={
                        "symbol": request.ts_code,
                        "period": f"{request.start:%Y%m%d}-{request.end:%Y%m%d}",
                    },
                )
            )
        return batches


def main() -> int:
    from shaiwei.config import load
    from shaiwei.ingest.catalog import canonical_params_key, committed_params_keys

    parser = argparse.ArgumentParser(description="筛微 S8 AKShare 独立源采集")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    settings = load()
    start = args.as_of - timedelta(days=settings.crosscheck.lookback_calendar_days)
    requests = [CrosscheckRequest(symbol, start, args.as_of) for symbol in settings.crosscheck.symbols]
    planned_count = len(requests)
    if args.resume:
        committed = committed_params_keys("akshare.stock_zh_a_hist")
        requests = [request for request in requests if canonical_params_key(request_params(request)) not in committed]
    summary = {
        "as_of": args.as_of.isoformat(),
        "planned_request_count": planned_count,
        "request_count": len(requests),
        "skipped_committed_count": planned_count - len(requests),
        "symbols": [request.ts_code for request in requests],
    }
    if args.dry_run or not requests:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    _add_no_proxy_host(EASTMONEY_API_HOST)
    batches = AKShareIngestor(
        RawBatchWriter(settings.runtime.data_root),
        max_attempts=settings.ingest.max_attempts,
        retry_base_seconds=settings.ingest.retry_base_seconds,
    ).run(requests)
    print(
        json.dumps(
            {**summary, "batch_count": len(batches), "row_count": sum(batch.row_count for batch in batches)},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
