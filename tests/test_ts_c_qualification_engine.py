from shaiwei.research.trend_swing.ts_c.cli import main
from shaiwei.research.trend_swing.ts_c.fixture import fixture
from shaiwei.research.trend_swing.ts_c.profile import evaluate_density


def test_episode_machine_paths() -> None:
    assert fixture()["fixture_pass"] is True


def test_density_gate_is_fail_closed_per_trigger() -> None:
    gate = {
        "per_trigger_minimum_confirmed_events": 120,
        "per_trigger_minimum_events_each_calendar_year": 10,
        "per_trigger_minimum_distinct_signal_days": 40,
    }
    events = [
        {"trigger_id": "HIGH20_DRAWDOWN", "ts_code": f"6000{index:02d}.SH",
         "signal_date": f"{2019 + index % 7}{1 + index % 12:02d}{1 + index % 27:02d}"}
        for index in range(150)
    ]
    report = evaluate_density(events, gate)
    assert report["per_trigger"]["HIGH20_DRAWDOWN"]["qualified"] is True
    assert report["per_trigger"]["MA20_PULLBACK"]["qualified"] is False
    assert report["verdict"] == "GO_TS_C_TOURNAMENT_PROTOCOL_DRAFT_ONLY"
    assert evaluate_density([], gate)["verdict"] == "STOP_TS_C_NO_DENSE_LEGAL_TRIGGER"


def test_cli_fixture_is_stable(capsys) -> None:
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
