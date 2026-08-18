from decimal import Decimal

import numpy as np
import pytest

from shaiwei.research.trend_swing.v6_1.cli import main
from shaiwei.research.trend_swing.v6_1.profile import fixture
from shaiwei.research.trend_swing.v6_1.score import (
    AXES,
    canonical_json,
    development_gate_report,
    holdout_gate_report,
    integration_report,
    iqr,
    map_reference_positions,
    mid_rank_positions,
    native,
    score_against_reference,
    score_events,
    select_by_cut,
    select_top_k,
)


def _event(index: int, role: str = "selectable_discovery") -> dict[str, object]:
    year = 2021 + index % 3 if role == "selectable_discovery" else 2024 + index % 2
    return {
        "role": role,
        "ts_code": f"{index:06d}.SZ",
        "signal_date": f"{year}{1 + index % 12:02d}{1 + index % 27:02d}",
        "next_open_date": f"{year}{1 + index % 12:02d}{2 + index % 26:02d}",
        "pullback_amount_ratio": (index % 30 + 1) / 10,
        "recovery_close_location": (index % 20 + 1) / 21,
        "pre_entry_10d_return_percentile": (index % 25 + 1) / 26,
    }


def test_mid_rank_positions_are_deterministic_and_handle_ties() -> None:
    positions = mid_rank_positions([Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4")])
    assert positions == (
        Decimal("0.12500000"),
        Decimal("0.50000000"),
        Decimal("0.50000000"),
        Decimal("0.87500000"),
    )
    assert mid_rank_positions(["1", "2", "2", "4"]) == positions
    with pytest.raises(ValueError, match="empty"):
        mid_rank_positions([])


def test_reference_mapping_uses_only_reference_sample() -> None:
    reference = [Decimal(str(value)) for value in (1.0, 2.0, 3.0, 4.0)]
    assert map_reference_positions(reference, [Decimal("10")]) == (Decimal("1.00000000"),)
    assert map_reference_positions(reference, [Decimal("0.5")]) == (Decimal("0.00000000"),)
    assert map_reference_positions(reference, [Decimal("2")]) == (Decimal("0.37500000"),)


def test_score_directions_match_frozen_economic_semantics() -> None:
    rows = [_event(index) for index in range(120)]
    for row in rows:
        row["pullback_amount_ratio"] = 1.0
        row["recovery_close_location"] = 0.5
        row["pre_entry_10d_return_percentile"] = 0.5
    rows[0]["pullback_amount_ratio"] = 0.5
    rows[1]["recovery_close_location"] = 0.9
    rows[2]["pre_entry_10d_return_percentile"] = 0.1
    scored = score_events(rows)
    by_code = {row["ts_code"]: row for row in scored}
    assert by_code["000000.SZ"]["axis_positions"]["pullback_amount_ratio"] > by_code["000003.SZ"]["axis_positions"]["pullback_amount_ratio"]
    assert by_code["000001.SZ"]["axis_positions"]["recovery_close_location"] > by_code["000003.SZ"]["axis_positions"]["recovery_close_location"]
    assert by_code["000002.SZ"]["axis_positions"]["pre_entry_10d_return_percentile"] > by_code["000003.SZ"]["axis_positions"]["pre_entry_10d_return_percentile"]


def test_top_k_selection_is_deterministic_and_cut_is_kth_score() -> None:
    scored = score_events([_event(index) for index in range(120)])
    selected, cut = select_top_k(scored, 94)
    assert len(selected) == 94
    assert selected[-1]["score"] == cut
    assert all(
        (selected[i]["score"],) >= (selected[i + 1]["score"],) for i in range(93)
    )
    replay, replay_cut = select_top_k(score_events([_event(index) for index in range(120)]), 94)
    assert canonical_json(selected) == canonical_json(replay) and cut == replay_cut
    with pytest.raises(ValueError, match="top-k"):
        select_top_k(scored, 121)


def test_holdout_cut_selection_and_integration_difference() -> None:
    development = [_event(index) for index in range(120)]
    holdout = [_event(index, "frozen_stability_holdout") for index in range(60)]
    scored = score_events(development)
    selected, cut = select_top_k(scored, 60)
    kept = select_by_cut(score_against_reference(development, holdout), cut)
    assert kept and all(row["score"] >= cut for row in kept)
    integration = integration_report(scored, selected, 60)
    assert set(integration) == set(AXES)
    assert any(integration.values())


def test_degenerate_dispersion_fails_closed() -> None:
    rows = [_event(index) for index in range(120)]
    for row in rows:
        row["recovery_close_location"] = 0.5
    scored = score_events(rows)
    selected, _ = select_top_k(scored, 60)
    gate = {"minimum_legal_events": 30, "minimum_distinct_signal_days": 20,
            "minimum_events_each_calendar_year": 5}
    report = development_gate_report(selected, scored, rows, gate, 60)
    assert report["checks"]["per_axis_interquartile_range_positive"] is False
    assert report["pass"] is False
    assert iqr([Decimal("0.5"), Decimal("0.5")]) == Decimal("0.00000000")


def test_gate_reports_respect_frozen_thresholds() -> None:
    development = [_event(index) for index in range(120)]
    scored = score_events(development)
    selected, _ = select_top_k(scored, 60)
    strict = {"minimum_legal_events": 90, "minimum_distinct_signal_days": 36,
              "minimum_events_each_calendar_year": 10}
    assert development_gate_report(selected, scored, development, strict, 60)["pass"] is False
    relaxed = {"minimum_legal_events": 60, "minimum_distinct_signal_days": 30,
               "minimum_events_each_calendar_year": 10}
    assert development_gate_report(selected, scored, development, relaxed, 60)["pass"] is True
    holdout = [_event(index, "frozen_stability_holdout") for index in range(60)]
    report = holdout_gate_report(
        holdout, {"minimum_distinct_signal_days": 20, "minimum_events_each_calendar_year": 10}
    )
    assert report["pass"] is True
    report = holdout_gate_report(
        holdout[:10], {"minimum_distinct_signal_days": 20, "minimum_events_each_calendar_year": 10}
    )
    assert report["pass"] is False


def test_library_scalars_and_cli_fixture_are_stable(capsys) -> None:
    normalized = native({"ok": np.bool_(True), "count": np.int64(9), "value": np.float64(0.5)})
    assert normalized == {"ok": True, "count": 9, "value": 0.5}
    canonical_json(normalized)
    assert fixture()["fixture_pass"] is True
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
