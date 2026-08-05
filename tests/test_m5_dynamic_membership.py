from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m5_dynamic.contract import M5DataProtocol, M5GateError
from shaiwei.research_gates.m5_dynamic.fixture import synthetic_inputs
from shaiwei.research_gates.m5_dynamic.membership import (
    build_membership_panel,
    formation_schedule,
)


ROOT = Path(__file__).parents[1]


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def test_sixty_months_map_to_one_strict_next_open() -> None:
    protocol = _protocol()
    frames, _ = synthetic_inputs(protocol)
    schedule = formation_schedule(
        frames["tushare.trade_cal"], start_month="2021-01", end_month="2025-12"
    )

    assert len(schedule) == 60
    assert schedule["formation_date"].str[:6].nunique() == 60
    assert schedule["effective_date"].gt(schedule["formation_date"]).all()
    assert schedule.iloc[0].to_dict() == {
        "formation_month": "2021-01",
        "formation_date": "20210129",
        "effective_date": "20210201",
    }


def test_membership_uses_effective_date_and_source_formation() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    panel, diagnostics = build_membership_panel(
        protocol, frames["tushare.trade_cal"], memberships
    )

    assert len(panel) == 60 * (30 + 20 + 20)
    assert panel["effective_date"].gt(panel["formation_date"]).all()
    assert panel["source_formation_date"].eq(panel["formation_date"]).all()
    assert diagnostics["formation_month_count"] == 60
    assert diagnostics["bse_rows"] == diagnostics["duplicate_keys"] == 0


def test_custom_member_from_wrong_formation_fails_closed() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    custom = memberships["star-board-midcap-pit-v1"].copy()
    custom.loc[custom.index[0], "formation_date"] = "20200131"
    memberships["star-board-midcap-pit-v1"] = custom

    with pytest.raises(M5GateError, match="source formation"):
        build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)


def test_duplicate_bj_and_missing_next_open_fail_closed() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    duplicate = pd.concat(
        [memberships["star50-official-pit-v2"], memberships["star50-official-pit-v2"].iloc[:1]],
        ignore_index=True,
    )
    memberships["star50-official-pit-v2"] = duplicate
    with pytest.raises(M5GateError, match="duplicate"):
        build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)

    frames, memberships = synthetic_inputs(protocol)
    memberships["star50-official-pit-v2"].loc[0, "ts_code"] = "839999.BJ"
    with pytest.raises(M5GateError, match="\.BJ"):
        build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)

    frames, memberships = synthetic_inputs(protocol)
    last = memberships["star50-official-pit-v2"]["trade_date"].max()
    memberships["star50-official-pit-v2"] = memberships[
        "star50-official-pit-v2"
    ].loc[lambda frame: frame["trade_date"].ne(last)]
    with pytest.raises(M5GateError, match="lacks exact next-open"):
        build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)
