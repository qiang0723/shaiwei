"""AKShare 独立源采集适配器，用于 S8 交叉比对。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from shaiwei.ingest.core import RawBatch, RawBatchWriter

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


class AKShareIngestor:
    def __init__(
        self,
        writer: RawBatchWriter,
        fetch: Callable[..., pd.DataFrame] | None = None,
    ) -> None:
        if fetch is None:
            import akshare as ak

            fetch = ak.stock_zh_a_hist
        self.writer = writer
        self.fetch = fetch

    def run(self, requests: list[CrosscheckRequest]) -> list[RawBatch]:
        batches = []
        for request in requests:
            params = {
                "symbol": request.ts_code.split(".", maxsplit=1)[0],
                "period": "daily",
                "start_date": request.start.strftime("%Y%m%d"),
                "end_date": request.end.strftime("%Y%m%d"),
                "adjust": "",
            }
            raw = self.fetch(**params)
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
