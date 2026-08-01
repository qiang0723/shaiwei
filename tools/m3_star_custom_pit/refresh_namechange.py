"""Refresh only frozen STAR-board name histories through the M3 source gate."""

from __future__ import annotations

import json

import pandas as pd

from shaiwei.config import load
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import Request, TushareIngestor, create_client

from tools.m3_star_custom_pit.contract import load_protocol
from tools.m3_star_custom_pit.inputs import latest_entries, load_stock_identity


def stale_namechange_codes(codes: tuple[str, ...], minimum: str) -> list[str]:
    code_set = set(codes)
    try:
        entries = latest_entries(
            "tushare.namechange",
            lambda params: str(params.get("ts_code", "")) in code_set,
        )
    except RuntimeError:
        return sorted(code_set)
    latest_by_code = {
        str(row["_params"].get("ts_code", "")): row["_time"]
        for _, row in entries.iterrows()
    }
    minimum_day = pd.Timestamp(minimum, tz="Asia/Shanghai").date()
    return sorted(
        code
        for code in code_set
        if code not in latest_by_code
        or latest_by_code[code].tz_convert("Asia/Shanghai").date() < minimum_day
    )


def run() -> dict[str, int]:
    protocol = load_protocol()
    _, codes, _ = load_stock_identity(protocol)
    minimum = protocol["sources"]["namechange_latest_ingest_date_minimum"]
    stale = stale_namechange_codes(codes, minimum)
    if not stale:
        return {"star_security_count": len(codes), "request_count": 0, "batch_count": 0, "row_count": 0}

    settings = load()
    client = create_client(settings.runtime.tushare_token.get_secret_value())
    requests = [
        Request("namechange", {"ts_code": code}, {"symbol": code})
        for code in stale
    ]
    batches = TushareIngestor(
        client=client,
        writer=RawBatchWriter(settings.runtime.data_root),
        settings=settings,
    ).run(requests)
    return {
        "star_security_count": len(codes),
        "request_count": len(requests),
        "batch_count": len(batches),
        "row_count": sum(batch.row_count for batch in batches),
    }


def main() -> int:
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
