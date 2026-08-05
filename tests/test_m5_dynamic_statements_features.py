from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m5_dynamic.contract import M5DataProtocol, M5GateError
from shaiwei.research_gates.m5_dynamic.features import calculate_features
from shaiwei.research_gates.m5_dynamic.fixture import synthetic_inputs
from shaiwei.research_gates.m5_dynamic.membership import build_membership_panel
from shaiwei.research_gates.m5_dynamic.statements import build_candidate_components


ROOT = Path(__file__).parents[1]


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _components(
    protocol: M5DataProtocol,
    frames: dict[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    if frames is None:
        frames, membership_frames = synthetic_inputs(protocol)
    else:
        _, membership_frames = synthetic_inputs(protocol)
    members, _ = build_membership_panel(
        protocol, frames["tushare.trade_cal"], membership_frames
    )
    components, _ = build_candidate_components(protocol, members, frames)
    return components, membership_frames


def test_candidate_specific_pairing_produces_exact_members_x_eight() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    members, _ = build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)
    components, diagnostics = build_candidate_components(protocol, members, frames)
    panel, feature_diagnostics = calculate_features(protocol, components)

    assert len(components) == len(members) * 8 == 33_600
    assert panel["value"].notna().all()
    assert panel["invalid_reason"].isna().all()
    assert diagnostics["future_availability_rows"] == 0
    assert feature_diagnostics["invalid_rows"] == 0


def test_missing_unrelated_cashflow_does_not_block_income_or_balance_candidates() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    code = memberships["star50-official-pit-v2"]["ts_code"].min()
    for api in ("tushare.cashflow", "tushare.cashflow_vip"):
        frames[api] = frames[api].loc[frames[api]["ts_code"].ne(code)].copy()
    members, _ = build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)
    components, _ = build_candidate_components(protocol, members, frames)
    latest = components.loc[
        components["ts_code"].eq(code) & components["formation_date"].eq("20251231")
    ]

    assert latest.loc[
        latest["candidate_id"].eq("m5_gross_margin_improvement_v1"), "current_end_date"
    ].eq("20241231").all()
    assert latest.loc[
        latest["candidate_id"].eq("m5_inventory_accumulation_v1"), "current_end_date"
    ].eq("20241231").all()
    assert latest.loc[
        latest["candidate_id"].isin(
            ["m5_external_financing_dependence_v1", "m5_free_cashflow_margin_improvement_v1"]
        ),
        "current_end_date",
    ].isna().all()


def test_external_financing_does_not_require_predecessor_cashflow() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    code = memberships["star50-official-pit-v2"]["ts_code"].min()
    for api in ("tushare.cashflow", "tushare.cashflow_vip"):
        frames[api] = frames[api].loc[
            ~(frames[api]["ts_code"].eq(code) & frames[api]["end_date"].eq("20231231"))
        ].copy()
    members, _ = build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)
    components, _ = build_candidate_components(protocol, members, frames)
    latest = components.loc[
        components["ts_code"].eq(code)
        & components["formation_date"].eq("20251231")
        & components["universe_id"].eq("star50-official-pit-v2")
    ]
    external = latest.loc[
        latest["candidate_id"].eq("m5_external_financing_dependence_v1")
    ].iloc[0]
    free_cashflow = latest.loc[
        latest["candidate_id"].eq("m5_free_cashflow_margin_improvement_v1")
    ].iloc[0]

    assert external["current_end_date"] == "20241231"
    assert external["predecessor_end_date"] == "20231231"
    assert free_cashflow["current_end_date"] == "20221231"
    assert free_cashflow["predecessor_end_date"] == "20211231"


def test_conflicting_ordinary_vip_identity_fails_closed() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    frames["tushare.income_vip"].loc[0, "total_revenue"] += 1.0
    members, _ = build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)

    with pytest.raises(M5GateError, match="conflicting duplicate"):
        build_candidate_components(protocol, members, frames)


def test_formula_values_are_raw_and_signed_cashflows_remain_valid() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    members, _ = build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)
    components, _ = build_candidate_components(protocol, members, frames)
    panel, _ = calculate_features(protocol, components)
    code = sorted(members["ts_code"].unique())[1]
    selector = (
        panel["ts_code"].eq(code)
        & panel["formation_date"].eq("20251231")
        & panel["universe_id"].eq("star50-official-pit-v2")
    )
    external = panel.loc[
        selector & panel["candidate_id"].eq("m5_external_financing_dependence_v1")
    ].iloc[0]

    assert external["invalid_reason"] is pd.NA or pd.isna(external["invalid_reason"])
    assert float(external["value"]) < 0
    assert next(
        candidate.expected_direction
        for candidate in protocol.candidates
        if candidate.candidate_id == external["candidate_id"]
    ) == -1


def test_staleness_denominator_missing_sign_and_negative_margin_boundaries() -> None:
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    members, _ = build_membership_panel(protocol, frames["tushare.trade_cal"], memberships)
    components, _ = build_candidate_components(protocol, members, frames)

    inventory = components.loc[
        components["candidate_id"].eq("m5_inventory_accumulation_v1")
    ].iloc[[0]].copy()
    inventory["staleness_days"] = 548
    valid, _ = calculate_features(protocol, inventory)
    assert valid["value"].notna().all()
    inventory["staleness_days"] = 549
    stale, _ = calculate_features(protocol, inventory)
    assert stale.iloc[0]["invalid_reason"] == "STALE_ANNUAL_PAIR"

    research = components.loc[
        components["candidate_id"].eq("m5_rd_intensity_improvement_v1")
    ].iloc[[0]].copy()
    research["component__income__rd_exp_t"] = pd.NA
    missing, _ = calculate_features(protocol, research)
    assert missing.iloc[0]["invalid_reason"] == "MISSING_COMPONENT"
    research["component__income__rd_exp_t"] = -1.0
    negative, _ = calculate_features(protocol, research)
    assert negative.iloc[0]["invalid_reason"] == "NEGATIVE_DISALLOWED_COMPONENT"
    research["component__income__rd_exp_t"] = 1.0
    research["component__income__total_revenue_t"] = 0.0
    denominator, _ = calculate_features(protocol, research)
    assert denominator.iloc[0]["invalid_reason"] == "INVALID_DENOMINATOR"

    gross = components.loc[
        components["candidate_id"].eq("m5_gross_margin_improvement_v1")
    ].iloc[[0]].copy()
    gross["component__income__total_cogs_t"] = (
        gross["component__income__total_revenue_t"] * 1.2
    )
    negative_margin, _ = calculate_features(protocol, gross)
    assert negative_margin["value"].notna().all()
    assert math.isfinite(float(negative_margin.iloc[0]["value"]))
