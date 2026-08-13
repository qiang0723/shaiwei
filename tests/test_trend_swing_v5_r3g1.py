from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_r3g1_audit import (
    _events_obey_frozen_roles,
    _profile_counts_match_events,
)
from shaiwei.research.trend_swing.v5_r3g1_contract import R3G1Scope, validate_bound_inputs
from shaiwei.research.trend_swing.v5_r3g1_features import prepare_role_stream
from shaiwei.research.trend_swing.v5_r3g1_inputs import next_open_input
from shaiwei.research.trend_swing.v5_r3g1_selection import (
    density_evidence,
    discovery_pass,
    parameter_hash,
    select_anchor,
    select_neighbours,
)
from shaiwei.research.trend_swing.v5_r3g_contract import R3GScope, registered_candidates


def _profile(point, yearly):
    events = [
        {"signal_date": f"{year}010{i + 1}"}
        for year, count in yearly.items()
        for i in range(count)
    ]
    evidence = density_evidence(events, (2021, 2022, 2023))
    return {
        "point_hash": parameter_hash(point),
        "parameters": point,
        "discovery": evidence,
        "discovery_pass": True,
    }


def test_scope_freezes_recent_role_separation_and_no_effect_authority():
    scope = R3G1Scope.load()
    validate_bound_inputs(scope)
    assert scope.roles == (
        ("selectable_discovery", "20210104", "20231229"),
        ("frozen_stability_holdout", "20240102", "20251231"),
        ("current_partial_year_monitor", "20260105", "20260811"),
    )
    assert scope.document["chronological_roles"]["current_partial_year_monitor"]["affects_verdict"] is False
    assert scope.document["authority"]["read_post_entry_return_or_effect"] is False
    assert scope.document["production_authorization"] == "none"
    assert scope.recovery["frozen_parent"]["observed_event_rows"] == 0
    assert scope.recovery["frozen_parent"]["authority_status"] == (
        "INVALIDATED_BY_COMMON_EXECUTION_PROJECTION_DEFECT"
    )
    assert scope.identity_recovery["provisional_image"]["image_process_started"] is False
    assert scope.identity_recovery["authority"]["additional_density_attempt"] is False


def test_scope_drift_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import shaiwei.research.trend_swing.v5_r3g1_contract as contract

    document = deepcopy(R3G1Scope.load().document)
    document["authority"]["read_post_entry_return_or_effect"] = True
    path = tmp_path / "scope.yaml"
    path.write_text("read_post_entry_return_or_effect: true\n", encoding="utf-8")
    monkeypatch.setattr(contract, "SCOPE_PATH", path)
    with pytest.raises(D1ControlError):
        R3G1Scope.load()


def test_density_gate_counts_only_required_years():
    evidence = density_evidence(
        [{"signal_date": f"{year}01{i + 1:02d}"} for year in (2021, 2022, 2023, 2026) for i in range(10)],
        (2021, 2022, 2023),
    )
    gate = R3G1Scope.load().document["density_gate"]
    assert evidence["legal_event_count"] == 30
    assert "2026" not in evidence["legal_event_count_by_calendar_year"]
    assert discovery_pass(evidence, gate)


def test_anchor_and_neighbours_are_mechanical_and_deterministic():
    registered = registered_candidates(R3GScope.load())[0]
    points = registered.grid[:4]
    profiles = [
        _profile(points[0], {2021: 20, 2022: 20, 2023: 20}),
        _profile(points[1], {2021: 15, 2022: 20, 2023: 25}),
        _profile(points[2], {2021: 10, 2022: 10, 2023: 10}),
        _profile(points[3], {2021: 6, 2022: 40, 2023: 40}),
    ]
    anchor = select_anchor(profiles)
    assert anchor["parameters"] == points[0]
    neighbours = select_neighbours(registered, anchor, profiles)
    assert len(neighbours) == 2
    assert [item["point_hash"] for item in neighbours] == [
        item["point_hash"] for item in select_neighbours(registered, anchor, profiles)
    ]


def test_new_modules_respect_architecture_size_budget():
    root = Path(__file__).resolve().parents[1] / "src/shaiwei/research/trend_swing"
    for path in root.glob("v5_r3g1_*.py"):
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 300, path.name


def test_r3g1_build_and_runtime_have_non_manual_identity_gates():
    root = Path(__file__).resolve().parents[1]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile.ts-v5-r3g1").read_text(encoding="utf-8")
    assert '"$$(git rev-parse HEAD)"' in makefile
    assert '"$$(git rev-parse origin/main)"' in makefile
    assert "SHAIWEI_RELEASE_MANIFEST=/opt/shaiwei/release-manifest.json" in dockerfile


def test_role_stream_projects_raw_open_and_marks_missing_security_bar():
    connection = duckdb.connect(":memory:")
    connection.execute(
        "CREATE TABLE r4_daily_context(ts_code VARCHAR,plan_week VARCHAR,industry VARCHAR,"
        "segment VARCHAR,segment_code VARCHAR,f_plan BOOLEAN)"
    )
    connection.execute("INSERT INTO r4_daily_context VALUES ('000001.SZ','20210108','BANK','MAIN','SZ',true)")
    connection.execute("CREATE TABLE open_days(trade_date VARCHAR,market_rank INTEGER)")
    connection.execute("INSERT INTO open_days VALUES ('20210104',1),('20210105',2)")
    connection.execute(
        "CREATE TABLE r3g1_feature_context(ts_code VARCHAR,trade_date VARCHAR,market_rank INTEGER,"
        "industry VARCHAR,segment VARCHAR,segment_code VARCHAR,plan_week VARCHAR,f_plan BOOLEAN,"
        "f_daily BOOLEAN,amount_rmb DOUBLE,adj_open DOUBLE,adj_factor DOUBLE)"
    )
    connection.execute(
        "INSERT INTO r3g1_feature_context VALUES "
        "('000001.SZ','20210104',1,'BANK','MAIN','SZ','20210108',true,true,1000,12,1.2)"
    )
    prepare_role_stream(connection)
    rows = connection.execute(
        "SELECT trade_date,has_bar,raw_open FROM r3g1_stream ORDER BY trade_date"
    ).fetchall()
    assert rows == [("20210104", True, 10.0), ("20210105", False, None)]


def test_missing_raw_open_fails_required_execution_projection():
    candidate = registered_candidates(R3GScope.load())[0].candidate
    point = registered_candidates(R3GScope.load())[0].grid[0]
    signal = {"f_daily": True, "adj_factor": Decimal("1")}
    row = {
        "adj_open": Decimal("10"), "adj_factor": Decimal("1"),
        "same_adjustment_factor": True, "role_sequence": 2,
        "liquidity_gate": True, "security_eligible": True,
    }
    with pytest.raises(KeyError, match="raw_open"):
        next_open_input(candidate, point, signal, row)


def test_independent_density_reconciliation_rejects_report_drift():
    event = {
        "role": "selectable_discovery", "candidate_ordinal": 1,
        "point_hash": "point", "ts_code": "000001.SZ",
        "signal_date": "20210104", "next_open_date": "20210105",
    }
    evidence = {
        "legal_event_count": 1, "distinct_signal_day_count": 1,
        "legal_event_count_by_calendar_year": {"2021": 1, "2022": 0, "2023": 0},
    }
    profile = [{
        "candidate_ordinal": 1,
        "point_profiles": [{"point_hash": "point", "discovery": evidence}],
        "selected_points": [],
    }]
    assert _profile_counts_match_events(profile, [event])
    profile[0]["point_profiles"][0]["discovery"]["legal_event_count"] = 2
    assert not _profile_counts_match_events(profile, [event])
    assert _events_obey_frozen_roles([event], R3G1Scope.load())
    event["ts_code"] = "830001.BJ"
    assert not _events_obey_frozen_roles([event], R3G1Scope.load())
