from shaiwei.research.trend_swing.ts_c.cli_v2 import main as main_v2
from shaiwei.research.trend_swing.ts_c.contract import TQC2Scope
from shaiwei.research.trend_swing.ts_c.profile_v2 import evaluate_density_v2, permission_on_years


def _day(day: str, on: bool) -> dict[str, object]:
    base = {"trade_date": day}
    if on:
        base.update({"index_prev_month_close": 4001.0, "index_prev_sma6": 4000.0,
                     "index_prev2_sma6": 3999.0})
    else:
        base.update({"index_prev_month_close": 3999.0, "index_prev_sma6": 4000.0,
                     "index_prev2_sma6": 4000.5})
    return base


def test_permission_on_years_rule_is_mechanical() -> None:
    rows = [_day(f"2021{index:02d}05", True) for index in range(1, 13)]
    rows += [_day(f"2022{index:02d}05", False) for index in range(1, 13)]
    rows += [_day(f"2023{index:02d}05", index % 2 == 0) for index in range(1, 13)]
    result = permission_on_years(rows)
    assert result["permission_on_years"] == ["2021", "2023"]


def test_density_v2_gates_only_permission_on_years() -> None:
    gate = {
        "per_trigger_minimum_confirmed_events": 120,
        "per_trigger_minimum_events_each_permission_on_calendar_year": 10,
        "per_trigger_minimum_distinct_signal_days": 40,
    }
    on_years = ["2019", "2020", "2021", "2023", "2024"]
    events = [
        {"trigger_id": "HIGH20_DRAWDOWN", "ts_code": f"6000{index:02d}.SH",
         "signal_date": f"{int(on_years[index % 5])}{1 + index % 12:02d}{1 + index % 27:02d}"}
        for index in range(150)
    ]
    events.append({"trigger_id": "HIGH20_DRAWDOWN", "ts_code": "600000.SH",
                   "signal_date": "20220115"})
    report = evaluate_density_v2(events, on_years, gate)
    assert report["per_trigger"]["HIGH20_DRAWDOWN"]["qualified"] is True
    assert report["verdict"] == "GO_TS_C_TOURNAMENT_PROTOCOL_DRAFT_ONLY"
    assert evaluate_density_v2([], on_years, gate)["verdict"] == "STOP_TS_C_NO_DENSE_LEGAL_TRIGGER"


def test_cli_v2_fixture_is_stable(capsys) -> None:
    assert main_v2(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out


def test_v2_scope_freezes_re_scoped_gate() -> None:
    scope = TQC2Scope.load()
    rule = scope.document["permission_on_year_rule"]
    assert rule["not_derived_from_event_counts"] is True
    assert rule["minimum_permission_on_years_required"] == 4
    assert scope.document["density_gate"][
        "per_trigger_minimum_events_each_permission_on_calendar_year"
    ] == 10
