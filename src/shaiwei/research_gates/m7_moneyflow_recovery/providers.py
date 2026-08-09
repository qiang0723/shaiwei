"""Dependency-injected provider adapters; this module never loads settings or secrets."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from .contract import RecoveryError, RecoveryProtocol
from .claims import ClaimedResult, RequestClaimIdentity, execute_claimed_request
from .planning import MoneyflowRequest, StatusRequest


class TushareQueryClient(Protocol):
    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame: ...


class BaostockQueryResult(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]

    def next(self) -> bool: ...
    def get_row_data(self) -> list[str]: ...


class BaostockQueryClient(Protocol):
    def query_history_k_data_plus(self, **kwargs: str) -> BaostockQueryResult: ...


def _baostock_code(ts_code: str) -> str:
    symbol, exchange = ts_code.split(".", maxsplit=1)
    if exchange not in {"SH", "SZ"}:
        raise RecoveryError("recovery status provider received unsupported exchange")
    return f"{exchange.lower()}.{symbol}"


def fetch_status(client: BaostockQueryClient, request: StatusRequest) -> pd.DataFrame:
    """Perform exactly one query on an already-authenticated injected client."""

    result = client.query_history_k_data_plus(
        code=_baostock_code(request.ts_code),
        fields="date,code,tradestatus",
        start_date=f"{request.start_date[:4]}-{request.start_date[4:6]}-{request.start_date[6:]}",
        end_date=f"{request.end_date[:4]}-{request.end_date[4:6]}-{request.end_date[6:]}",
        frequency="d",
        adjustflag="3",
    )
    if str(result.error_code) != "0":
        raise RecoveryError("recovery Baostock request failed semantically")
    rows: list[list[str]] = []
    while result.next():
        rows.append(result.get_row_data())
    frame = pd.DataFrame(rows, columns=result.fields)
    if frame.empty:
        return pd.DataFrame(columns=("ts_code", "trade_date", "trade_status"))
    if set(frame.columns) != {"date", "code", "tradestatus"}:
        raise RecoveryError("recovery Baostock response schema differs")
    expected_code = _baostock_code(request.ts_code)
    if set(frame["code"].astype(str)) != {expected_code}:
        raise RecoveryError("recovery Baostock response code differs")
    dates = pd.to_datetime(frame["date"], errors="raise").dt.strftime("%Y%m%d")
    if not set(dates) <= set(request.required_dates):
        raise RecoveryError("recovery Baostock response contains unrequested dates")
    normalized = pd.DataFrame(
        {
            "ts_code": request.ts_code,
            "trade_date": dates,
            "trade_status": frame["tradestatus"].astype(str).str.strip(),
        }
    )
    return normalized.sort_values("trade_date").reset_index(drop=True)


def fetch_moneyflow(
    client: TushareQueryClient,
    protocol: RecoveryProtocol,
    request: MoneyflowRequest,
) -> pd.DataFrame:
    """Perform one primary Tushare moneyflow query with the frozen field list."""

    fields = protocol.moneyflow_fields
    frame = client.query("moneyflow", **request.params, fields=",".join(fields))
    if not isinstance(frame, pd.DataFrame):
        raise RecoveryError("recovery Tushare response is not a table")
    if frame.empty:
        return pd.DataFrame(columns=fields)
    if set(frame.columns) != set(fields) or len(frame.columns) != len(fields):
        raise RecoveryError("recovery Tushare response schema differs")
    normalized = frame.loc[:, fields].copy()
    normalized["ts_code"] = normalized["ts_code"].astype("string")
    normalized["trade_date"] = normalized["trade_date"].astype("string")
    return normalized.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)


def collect_status(
    claim_root: Path,
    *,
    release_scope_sha256: str,
    client: BaostockQueryClient,
    request: StatusRequest,
) -> ClaimedResult[pd.DataFrame]:
    identity = RequestClaimIdentity(release_scope_sha256, request.identity_sha256)
    return execute_claimed_request(
        claim_root,
        identity,
        lambda: fetch_status(client, request),
        lambda frame: frame,
    )


def collect_moneyflow(
    claim_root: Path,
    *,
    release_scope_sha256: str,
    client: TushareQueryClient,
    protocol: RecoveryProtocol,
    request: MoneyflowRequest,
) -> ClaimedResult[pd.DataFrame]:
    identity = RequestClaimIdentity(release_scope_sha256, request.identity_sha256)
    return execute_claimed_request(
        claim_root,
        identity,
        lambda: fetch_moneyflow(client, protocol, request),
        lambda frame: frame,
    )
