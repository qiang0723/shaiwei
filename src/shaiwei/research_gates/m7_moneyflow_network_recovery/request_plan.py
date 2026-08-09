"""Typed deterministic request plans for the exact M7 recovery keys."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import (
    RecoveryError,
    RecoveryProtocol,
)
from shaiwei.research_gates.m7_moneyflow_recovery.planning import (
    MoneyflowRequest,
    StatusRequest,
    plan_moneyflow_requests,
    plan_status_requests,
    request_summary,
)
from shaiwei.research_gates.m7_moneyflow_recovery.target_projection import (
    recovery_request_targets,
)

from .network_contract import NetworkReleaseProtocol


STATUS_COLUMNS = (
    "request_sha256",
    "ts_code",
    "start_date",
    "end_date",
    "required_dates_json",
)
FULL_MARKET_COLUMNS = ("request_sha256", "trade_date")
TARGETED_COLUMNS = ("request_sha256", "ts_code", "start_date", "end_date")


@dataclass(frozen=True)
class RequestPlanData:
    status_requests: tuple[StatusRequest, ...]
    full_market_requests: tuple[MoneyflowRequest, ...]
    targeted_requests: tuple[MoneyflowRequest, ...]
    official_dates: tuple[str, ...]

    @property
    def moneyflow_requests(self) -> tuple[MoneyflowRequest, ...]:
        return self.full_market_requests + self.targeted_requests


def build_request_plan(
    network: NetworkReleaseProtocol,
    recovery: RecoveryProtocol,
    *,
    projected_track_a: pd.DataFrame,
    projected_track_b: pd.DataFrame,
    official_dates: tuple[str, ...],
) -> RequestPlanData:
    """Project sealed source keys and build the exact three request streams."""

    a = recovery_request_targets(projected_track_a)
    b = recovery_request_targets(projected_track_b)
    a_keys = a.drop_duplicates(["ts_code", "trade_date"])
    b_keys = b.drop_duplicates(["ts_code", "trade_date"])
    expected = network.document["request_plan_contract"]
    if (
        len(a_keys) != int(expected["track_a"]["expected_unique_keys"])
        or len(b_keys) != int(expected["track_b"]["expected_unique_keys"])
        or a_keys["ts_code"].str.endswith(".BJ").any()
        or b_keys["ts_code"].str.endswith(".BJ").any()
    ):
        raise RecoveryError("recovery network target key counts or exchange differ")
    status = tuple(plan_status_requests(recovery, a, official_dates))
    moneyflow = tuple(plan_moneyflow_requests(recovery, b))
    full = tuple(item for item in moneyflow if item.shape == "full_market_by_trade_date")
    targeted = tuple(item for item in moneyflow if item.shape == "one_security_one_date")
    covered = {
        (request.ts_code, day)
        for request in status
        for day in request.required_dates
    }
    if covered != set(a_keys[["ts_code", "trade_date"]].itertuples(index=False, name=None)):
        raise RecoveryError("recovery status plan does not cover exact target keys")
    if len(targeted) != len(b_keys):
        raise RecoveryError("recovery targeted moneyflow plan count differs")
    return RequestPlanData(status, full, targeted, tuple(official_dates))


def status_frame(requests: tuple[StatusRequest, ...]) -> pd.DataFrame:
    rows = [
        {
            "request_sha256": item.identity_sha256,
            "ts_code": item.ts_code,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "required_dates_json": canonical_json(list(item.required_dates)),
        }
        for item in requests
    ]
    return pd.DataFrame(rows, columns=STATUS_COLUMNS).astype("string")


def full_market_frame(requests: tuple[MoneyflowRequest, ...]) -> pd.DataFrame:
    rows = [
        {"request_sha256": item.identity_sha256, "trade_date": item.params["trade_date"]}
        for item in requests
    ]
    return pd.DataFrame(rows, columns=FULL_MARKET_COLUMNS).astype("string")


def targeted_frame(requests: tuple[MoneyflowRequest, ...]) -> pd.DataFrame:
    rows = [
        {
            "request_sha256": item.identity_sha256,
            "ts_code": item.params["ts_code"],
            "start_date": item.params["start_date"],
            "end_date": item.params["end_date"],
        }
        for item in requests
    ]
    return pd.DataFrame(rows, columns=TARGETED_COLUMNS).astype("string")


def _records(frame: pd.DataFrame, columns: tuple[str, ...]) -> list[dict[str, str]]:
    normalized = frame.loc[:, columns].astype("string")
    return [
        {column: str(value) for column, value in row.items()}
        for row in normalized.to_dict("records")
    ]


def frame_logical_sha256(frame: pd.DataFrame, columns: tuple[str, ...]) -> str:
    return sha256_json(_records(frame, columns))


def parse_status_frame(frame: pd.DataFrame) -> tuple[StatusRequest, ...]:
    if tuple(frame.columns) != STATUS_COLUMNS:
        raise RecoveryError("recovery status request plan schema differs")
    requests = []
    for row in frame.astype("string").itertuples(index=False):
        dates = json.loads(str(row.required_dates_json))
        if not isinstance(dates, list) or not dates:
            raise RecoveryError("recovery status request dates differ")
        request = StatusRequest(
            str(row.ts_code), str(row.start_date), str(row.end_date), tuple(map(str, dates))
        )
        if request.identity_sha256 != str(row.request_sha256):
            raise RecoveryError("recovery status request identity differs")
        requests.append(request)
    return tuple(requests)


def parse_full_market_frame(frame: pd.DataFrame) -> tuple[MoneyflowRequest, ...]:
    if tuple(frame.columns) != FULL_MARKET_COLUMNS:
        raise RecoveryError("recovery full-market request plan schema differs")
    requests = []
    for row in frame.astype("string").itertuples(index=False):
        request = MoneyflowRequest("full_market_by_trade_date", {"trade_date": str(row.trade_date)})
        if request.identity_sha256 != str(row.request_sha256):
            raise RecoveryError("recovery full-market request identity differs")
        requests.append(request)
    return tuple(requests)


def parse_targeted_frame(frame: pd.DataFrame) -> tuple[MoneyflowRequest, ...]:
    if tuple(frame.columns) != TARGETED_COLUMNS:
        raise RecoveryError("recovery targeted request plan schema differs")
    requests = []
    for row in frame.astype("string").itertuples(index=False):
        request = MoneyflowRequest(
            "one_security_one_date",
            {
                "ts_code": str(row.ts_code),
                "start_date": str(row.start_date),
                "end_date": str(row.end_date),
            },
        )
        if request.identity_sha256 != str(row.request_sha256):
            raise RecoveryError("recovery targeted request identity differs")
        requests.append(request)
    return tuple(requests)


def aggregate_summary(data: RequestPlanData) -> dict[str, Any]:
    return {
        "status": {
            **request_summary(list(data.status_requests)),
            "required_key_count": sum(len(item.required_dates) for item in data.status_requests),
            "maximum_window_key_count": max(map(lambda item: len(item.required_dates), data.status_requests)),
        },
        "full_market": request_summary(list(data.full_market_requests)),
        "targeted": request_summary(list(data.targeted_requests)),
        "official_dates": {
            "date_count": len(data.official_dates),
            "date_min": min(data.official_dates),
            "date_max": max(data.official_dates),
            "logical_sha256": sha256_json(list(data.official_dates)),
        },
    }
