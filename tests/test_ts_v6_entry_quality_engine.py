from decimal import Decimal

import numpy as np
import pytest

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_r3g1_selection import parameter_hash
from shaiwei.research.trend_swing.v6.cli import main
from shaiwei.research.trend_swing.v6.engine import (
    AXES,
    L9,
    canonical_json,
    density,
    derive_levels,
    design_points,
    development_eligible,
    filter_events,
    linear_quantile,
    native,
    select_point,
)
from shaiwei.research.trend_swing.v6.observations import (
    PARENT_POINT,
    PARENT_POINT_HASH,
    reconcile_parent_keys,
)
from shaiwei.research.trend_swing.v6.profile import fixture


def _observation(index: int, role: str = "selectable_discovery") -> dict[str, object]:
    year = 2021 + index % 3 if role == "selectable_discovery" else 2024 + index % 2
    return {
        "role": role,
        "ts_code": f"{index:06d}.SZ",
        "signal_date": f"{year}{1 + index % 12:02d}{1 + index % 27:02d}",
        "next_open_date": f"{year}{1 + index % 12:02d}{2 + index % 26:02d}",
        "pullback_amount_ratio": Decimal(index + 1) / 100,
        "recovery_close_location": Decimal(index + 1) / 200,
        "pre_entry_10d_return_percentile": Decimal(index + 1) / 181,
    }


def test_linear_quantile_is_deterministic_and_rounded_to_eight_places() -> None:
    assert linear_quantile([1, 2, 3, 4], "0.40") == Decimal("2.20000000")
    assert linear_quantile([Decimal("0.1"), Decimal("0.2")], "0.75") == Decimal("0.17500000")


def test_levels_and_fixed_l9_are_unique() -> None:
    levels = derive_levels([_observation(index) for index in range(180)])
    points = design_points(levels)
    assert tuple(tuple(row["level_indices"]) for row in points) == L9
    assert len({row["point_hash"] for row in points}) == 9
    assert all(set(row["parameters"]) == set(AXES) for row in points)


def test_level_collapse_fails_closed() -> None:
    rows = [_observation(index) for index in range(20)]
    for row in rows:
        row["recovery_close_location"] = Decimal("0.5")
    with pytest.raises(ValueError, match="LEVEL_COLLAPSE"):
        derive_levels(rows)


def test_filter_is_strict_parent_subset_and_reports_each_axis() -> None:
    rows = [_observation(index) for index in range(180)]
    levels = derive_levels(rows)
    point = design_points(levels)[4]
    accepted, reasons, axis_rejected = filter_events(rows, point["parameters"])
    parent_keys = {(row["ts_code"], row["signal_date"], row["next_open_date"]) for row in rows}
    child_keys = {(row["ts_code"], row["signal_date"], row["next_open_date"]) for row in accepted}
    assert child_keys < parent_keys
    assert all(value > 0 for value in axis_rejected.values())
    assert sum(reasons.values()) + len(accepted) == len(rows)


def test_density_and_mechanical_selection_use_frozen_order() -> None:
    base = {
        "parameters": {axis: "0.5" for axis in AXES},
        "development_pass": True,
    }
    profiles = []
    for index, yearly in enumerate(((35, 40, 45), (40, 40, 40), (42, 42, 42))):
        profiles.append({
            **base,
            "point_hash": chr(97 + index) * 64,
            "level_indices": [1, 1, index],
            "development": {
                "legal_event_count": sum(yearly),
                "distinct_signal_day_count": 40,
                "legal_event_count_by_calendar_year": dict(zip(("2021", "2022", "2023"), yearly)),
            },
        })
    assert select_point(profiles)["point_hash"] == "c" * 64
    evidence = density([_observation(index) for index in range(120)], (2021, 2022, 2023))
    passed, retention = development_eligible(
        evidence, 180, {axis: 1 for axis in AXES},
        {"minimum_legal_events": 90, "minimum_distinct_signal_days": 36,
         "minimum_events_each_calendar_year": 10, "retention_minimum": 0.3,
         "retention_maximum": 0.9},
    )
    assert passed and retention == pytest.approx(2 / 3)


def test_parent_point_hash_and_exact_key_reconciliation() -> None:
    assert parameter_hash(PARENT_POINT) == PARENT_POINT_HASH
    row = _observation(1)
    expected = {"selectable_discovery": {
        (str(row["ts_code"]), str(row["signal_date"]), str(row["next_open_date"]))
    }}
    reconcile_parent_keys([row], expected)
    with pytest.raises(D1ControlError, match="differ"):
        reconcile_parent_keys([], expected)


def test_library_scalars_and_cli_fixture_are_stable(capsys) -> None:
    normalized = native({"ok": np.bool_(True), "count": np.int64(9), "value": np.float64(0.5)})
    assert normalized == {"ok": True, "count": 9, "value": 0.5}
    canonical_json(normalized)
    assert fixture()["fixture_pass"] is True
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
