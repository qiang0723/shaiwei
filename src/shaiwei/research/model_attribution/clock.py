"""Official-calendar maturity checks for the frozen t+11 open label."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import AttributionError


def _compact_date(value: str) -> str:
    try:
        return datetime.strptime(str(value).replace("-", ""), "%Y%m%d").strftime("%Y%m%d")
    except ValueError as error:
        raise AttributionError(f"invalid M6 date: {value}") from error


def load_calendar(path: Path) -> tuple[str, ...]:
    dates = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if not dates or dates != tuple(sorted(set(dates))):
        raise AttributionError("M6 calendar is empty, duplicated, or unsorted")
    if any(_compact_date(value) != value for value in dates):
        raise AttributionError("M6 calendar contains a non-canonical date")
    return dates


def mature_last_signal(calendar: tuple[str, ...], segment_end: str, horizon: int) -> str:
    if horizon < 1:
        raise AttributionError("M6 label horizon must be positive")
    end = _compact_date(segment_end)
    available = [value for value in calendar if value <= end]
    if len(available) <= horizon:
        raise AttributionError("M6 calendar lacks label-maturity history")
    return available[-(horizon + 1)]


def verify_frozen_windows(protocol: dict[str, Any], calendar: tuple[str, ...]) -> list[dict[str, str]]:
    clock = protocol["clock_and_label"]
    horizon = int(clock["label_horizon_trade_days"])
    if horizon != 11:
        raise AttributionError("M6 label horizon differs from 11 trade days")
    verified: list[dict[str, str]] = []
    for window in protocol["windows"]:
        checks = {
            "purged_train_last_signal": mature_last_signal(calendar, window["train"][1], horizon),
            "purged_valid_last_signal": mature_last_signal(calendar, window["valid"][1], horizon),
            "score_last_signal": mature_last_signal(calendar, window["test"][1], horizon),
        }
        if any(str(window[key]).replace("-", "") != value for key, value in checks.items()):
            raise AttributionError(f"M6 label-maturity boundary differs: {window['name']}")
        verified.append(
            {
                "window": str(window["name"]),
                **{key: datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d") for key, value in checks.items()},
            }
        )
    return verified
