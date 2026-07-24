"""Official-calendar label-maturity purge for the frozen eleven-day label."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools.p2_star50_effect_correction.contract import CorrectionGateFailure


LABEL_HORIZON_TRADE_DAYS = 11


def official_calendar(benchmark: pd.DataFrame) -> list[str]:
    """Return a unique, ordered YYYYMMDD official index trading calendar."""
    if "trade_date" not in benchmark:
        raise CorrectionGateFailure("benchmark is missing trade_date")
    dates = pd.to_datetime(benchmark["trade_date"].astype("string"), errors="raise")
    rendered = dates.dt.strftime("%Y%m%d")
    if rendered.duplicated().any():
        raise CorrectionGateFailure("official benchmark calendar contains duplicate dates")
    calendar = rendered.sort_values().tolist()
    if not calendar:
        raise CorrectionGateFailure("official benchmark calendar is empty")
    return calendar


def _date_key(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def _last_on_or_before(calendar: list[str], endpoint: object) -> tuple[int, str]:
    key = _date_key(endpoint)
    candidates = [index for index, day in enumerate(calendar) if day <= key]
    if not candidates:
        raise CorrectionGateFailure(f"calendar has no date on or before {key}")
    index = candidates[-1]
    return index, calendar[index]


def purge_segment(
    segment: list[str] | tuple[str, str],
    calendar: list[str],
    *,
    horizon: int = LABEL_HORIZON_TRADE_DAYS,
) -> dict[str, Any]:
    """Purge the final ``horizon`` signal dates without moving the original endpoint."""
    if horizon <= 0:
        raise CorrectionGateFailure("label horizon must be positive")
    start, end = map(str, segment)
    endpoint_index, endpoint = _last_on_or_before(calendar, end)
    purged_index = endpoint_index - horizon
    if purged_index < 0:
        raise CorrectionGateFailure("segment endpoint lacks the frozen label-maturity history")
    purged_signal = calendar[purged_index]
    if purged_signal < _date_key(start):
        raise CorrectionGateFailure("label purge would empty the segment")
    maturity = calendar[purged_index + horizon]
    if maturity > endpoint:
        raise CorrectionGateFailure("purged label matures after the original segment endpoint")
    unpurged_maturity_index = endpoint_index + horizon
    if unpurged_maturity_index >= len(calendar):
        raise CorrectionGateFailure("calendar cannot demonstrate the unpurged boundary leak")
    return {
        "original_start": _date_key(start),
        "original_calendar_end": endpoint,
        "purged_last_signal": purged_signal,
        "purged_label_maturity": maturity,
        "unpurged_last_signal": endpoint,
        "unpurged_label_maturity": calendar[unpurged_maturity_index],
        "purged_signal_date_count": horizon,
    }


def purged_window_segments(
    window: dict[str, Any],
    calendar: list[str],
    required_dates: dict[str, str] | None = None,
) -> tuple[dict[str, tuple[str, str]], dict[str, Any]]:
    """Build purged train/valid and unchanged test segments with an audit record."""
    train = purge_segment(window["train"], calendar)
    valid = purge_segment(window["valid"], calendar)
    if required_dates:
        actual = {
            "train": train["purged_last_signal"],
            "valid": valid["purged_last_signal"],
        }
        expected = {key: _date_key(value) for key, value in required_dates.items()}
        if actual != expected:
            raise CorrectionGateFailure(
                f"purged segment dates differ from the frozen correction protocol: {actual} != {expected}"
            )
    first_test_date = min(day for day in calendar if day >= _date_key(window["test"][0]))
    if valid["purged_label_maturity"] >= first_test_date:
        raise CorrectionGateFailure("valid label maturity is not strictly before the first test date")
    segments = {
        "train": (
            pd.Timestamp(window["train"][0]).strftime("%Y-%m-%d"),
            pd.Timestamp(train["purged_last_signal"]).strftime("%Y-%m-%d"),
        ),
        "valid": (
            pd.Timestamp(window["valid"][0]).strftime("%Y-%m-%d"),
            pd.Timestamp(valid["purged_last_signal"]).strftime("%Y-%m-%d"),
        ),
        "test": tuple(pd.Timestamp(value).strftime("%Y-%m-%d") for value in window["test"]),
    }
    audit = {
        "window": str(window["name"]),
        "label_horizon_trade_days": LABEL_HORIZON_TRADE_DAYS,
        "train": train,
        "valid": valid,
        "first_test_trade_date": first_test_date,
        "train_label_maturity_within_original_segment": (
            train["purged_label_maturity"] <= train["original_calendar_end"]
        ),
        "valid_label_maturity_within_original_segment": (
            valid["purged_label_maturity"] <= valid["original_calendar_end"]
        ),
        "valid_label_maturity_before_test": valid["purged_label_maturity"] < first_test_date,
        "original_unpurged_train_would_cross_boundary": (
            train["unpurged_label_maturity"] > train["original_calendar_end"]
        ),
        "original_unpurged_valid_would_cross_boundary": (
            valid["unpurged_label_maturity"] >= first_test_date
        ),
    }
    if not all(
        audit[key]
        for key in (
            "train_label_maturity_within_original_segment",
            "valid_label_maturity_within_original_segment",
            "valid_label_maturity_before_test",
            "original_unpurged_train_would_cross_boundary",
            "original_unpurged_valid_would_cross_boundary",
        )
    ):
        raise CorrectionGateFailure(f"label-maturity audit failed for {window['name']}")
    return segments, audit
