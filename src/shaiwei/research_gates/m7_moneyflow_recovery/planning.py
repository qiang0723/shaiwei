"""Exact-target request planning without provider I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

from .contract import RecoveryError, RecoveryProtocol


CODE_RE = re.compile(r"^[0-9]{6}\.SH$")
DATE_RE = re.compile(r"^[0-9]{8}$")


@dataclass(frozen=True)
class StatusRequest:
    ts_code: str
    start_date: str
    end_date: str
    required_dates: tuple[str, ...]

    @property
    def identity_sha256(self) -> str:
        return sha256_json(
            {
                "source_api": "baostock.history_k_data_plus",
                "ts_code": self.ts_code,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "required_dates": list(self.required_dates),
            }
        )


@dataclass(frozen=True)
class MoneyflowRequest:
    shape: str
    params: dict[str, str]

    @property
    def identity_sha256(self) -> str:
        return sha256_json(
            {"source_api": "tushare.moneyflow", "shape": self.shape, "params": self.params}
        )


def _unique_keys(targets: pd.DataFrame) -> pd.DataFrame:
    required = {"ts_code", "trade_date"}
    if not required <= set(targets.columns):
        raise RecoveryError("recovery targets lack ts_code or trade_date")
    keys = targets.loc[:, ["ts_code", "trade_date"]].astype("string").drop_duplicates()
    invalid = ~keys["ts_code"].fillna("").str.fullmatch(CODE_RE) | ~keys[
        "trade_date"
    ].fillna("").str.fullmatch(DATE_RE)
    if invalid.any():
        raise RecoveryError("recovery request plan contains invalid target keys")
    return keys.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)


def _ordered_dates(official_dates: tuple[str, ...]) -> tuple[list[str], dict[str, int]]:
    ordered = list(official_dates)
    if ordered != sorted(set(ordered)) or any(DATE_RE.fullmatch(day) is None for day in ordered):
        raise RecoveryError("recovery official dates are invalid, duplicated, or unordered")
    return ordered, {day: position for position, day in enumerate(ordered)}


def plan_status_requests(
    protocol: RecoveryProtocol,
    targets: pd.DataFrame,
    official_dates: tuple[str, ...],
) -> list[StatusRequest]:
    """Group only consecutive exact target dates for each security."""

    keys = _unique_keys(targets)
    _, positions = _ordered_dates(official_dates)
    if missing := sorted(set(keys["trade_date"].astype(str)) - set(positions)):
        raise RecoveryError(f"recovery status targets are outside official dates: {len(missing)}")
    requests: list[StatusRequest] = []
    for code, group in keys.groupby("ts_code", sort=True):
        dates = group["trade_date"].astype(str).tolist()
        current = [dates[0]]
        for day in dates[1:]:
            if positions[day] == positions[current[-1]] + 1:
                current.append(day)
            else:
                requests.append(StatusRequest(str(code), current[0], current[-1], tuple(current)))
                current = [day]
        requests.append(StatusRequest(str(code), current[0], current[-1], tuple(current)))
    maximum = int(protocol.document["track_a_independent_trade_status"]["maximum_provider_requests"])
    if len(requests) > maximum:
        raise RecoveryError("recovery status request budget exceeded")
    if {key for request in requests for key in ((request.ts_code, day) for day in request.required_dates)} != set(
        keys.itertuples(index=False, name=None)
    ):
        raise RecoveryError("recovery status request plan is not an exact key partition")
    return requests


def plan_moneyflow_requests(
    protocol: RecoveryProtocol,
    targets: pd.DataFrame,
) -> list[MoneyflowRequest]:
    """Create one date-wide and one targeted request identity per required key."""

    keys = _unique_keys(targets)
    requests = [
        MoneyflowRequest("full_market_by_trade_date", {"trade_date": day})
        for day in sorted(set(keys["trade_date"].astype(str)))
    ]
    requests.extend(
        MoneyflowRequest(
            "one_security_one_date",
            {"ts_code": str(row.ts_code), "start_date": str(row.trade_date), "end_date": str(row.trade_date)},
        )
        for row in keys.itertuples(index=False)
    )
    frozen = protocol.document["track_b_same_semantic_moneyflow"]
    counts = {
        shape: sum(request.shape == shape for request in requests)
        for shape in ("full_market_by_trade_date", "one_security_one_date")
    }
    if (
        counts["full_market_by_trade_date"] > int(frozen["maximum_full_market_requests"])
        or counts["one_security_one_date"] > int(frozen["maximum_targeted_requests"])
        or len(requests) > int(frozen["maximum_provider_requests"])
    ):
        raise RecoveryError("recovery moneyflow request budget exceeded")
    if len({request.identity_sha256 for request in requests}) != len(requests):
        raise RecoveryError("recovery moneyflow request identities are not unique")
    return requests


def request_summary(requests: list[StatusRequest | MoneyflowRequest]) -> dict[str, Any]:
    return {
        "request_count": len(requests),
        "request_identity_bundle_sha256": sha256_json(
            [request.identity_sha256 for request in requests]
        ),
    }
