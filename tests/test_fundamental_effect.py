from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_effect.contract import (
    CandidateSpec,
    FundamentalEffectError,
    FundamentalEffectProtocol,
)
from shaiwei.research.fundamental_effect.io import write_json_once
from shaiwei.research.fundamental_effect.metrics import evaluate_discovery
from shaiwei.research.fundamental_effect.panel import (
    expand_monthly_features,
    formalize_panel,
    residualize_candidates,
)


CANDIDATES = (
    "fundamental_net_income_to_assets_v2",
    "fundamental_operating_margin_v2",
    "fundamental_cash_return_on_assets_v2",
    "fundamental_leverage_v2",
    "fundamental_cash_to_assets_v2",
    "fundamental_accruals_to_assets_v2",
)


def test_protocol_is_bound_to_the_frozen_bytes(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "config" / "f1_csi800_fundamental_effect_v1.yaml"
    frozen = tmp_path / "protocol.yaml"
    frozen.write_bytes(source.read_bytes())
    protocol = FundamentalEffectProtocol.load(frozen)
    assert [candidate.name for candidate in protocol.candidates] == list(CANDIDATES)
    assert [candidate.direction for candidate in protocol.candidates] == [1, 1, 1, -1, 1, -1]

    frozen.write_text(frozen.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(FundamentalEffectError, match="protocol hash differs"):
        FundamentalEffectProtocol.load(frozen)


def test_monthly_features_are_forward_held_without_future_backfill() -> None:
    rows = []
    for formation, codes, value in (
        ("20200131", ("600001.SH", "600002.SH"), 1.0),
        ("20200228", ("600002.SH", "600003.SH"), 2.0),
    ):
        for code in codes:
            row = {"formation_date": formation, "ts_code": code}
            row.update({candidate: value for candidate in CANDIDATES})
            rows.append(row)
    expanded = expand_monthly_features(
        pd.DataFrame(rows),
        ["20200131", "20200203", "20200228", "20200302"],
        start_date="20200131",
        end_date="20200302",
        candidate_names=CANDIDATES,
    )
    assert not expanded["source_formation_date"].gt(expanded["trade_date"]).any()
    assert set(expanded.loc[expanded["trade_date"].eq("20200203"), "ts_code"]) == {
        "600001.SH",
        "600002.SH",
    }
    assert set(expanded.loc[expanded["trade_date"].eq("20200302"), "ts_code"]) == {
        "600002.SH",
        "600003.SH",
    }


def _residual_fixture() -> pd.DataFrame:
    rows = []
    for day_offset, trade_date in enumerate(("20200102", "20200103", "20200106")):
        for index in range(40):
            value = index / 10 + day_offset
            row = {
                "ts_code": f"{600000 + index:06d}.SH",
                "trade_date": trade_date,
                "source_formation_date": "20191231",
                "industry": "A" if index < 20 else "B",
                "market_cap": float(np.exp(10 + index / 100)),
                "baseline_score": float((index % 7) - 3),
            }
            row.update(
                {
                    candidate: value + candidate_index / 100
                    for candidate_index, candidate in enumerate(CANDIDATES)
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def test_residualization_is_deterministic_and_formal_replacement_is_exact() -> None:
    fixture = _residual_fixture()
    core_first = residualize_candidates(
        fixture,
        candidate_names=CANDIDATES,
        include_baseline_score=False,
    )
    core_second = residualize_candidates(
        fixture.sample(frac=1.0, random_state=7),
        candidate_names=CANDIDATES,
        include_baseline_score=False,
    )
    pd.testing.assert_frame_equal(core_first, core_second)
    incremental = residualize_candidates(
        fixture.loc[fixture["trade_date"].eq("20200103")],
        candidate_names=CANDIDATES,
        include_baseline_score=True,
    )
    formal = formalize_panel(
        core_first,
        incremental,
        oos_start="20200103",
        oos_end="20200103",
    )
    assert len(formal) == len(core_first)
    pd.testing.assert_frame_equal(
        formal.loc[formal["trade_date"].eq("20200103")].reset_index(drop=True),
        incremental.reset_index(drop=True),
    )


def test_pre_registered_direction_rejects_instead_of_flipping() -> None:
    dates = pd.bdate_range("2017-01-02", periods=300)
    panel_rows = []
    label_index = []
    label_values = []
    for trade_date in dates:
        for index in range(40):
            code = f"{600000 + index:06d}.SH"
            panel_rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date.strftime("%Y%m%d"),
                    "fundamental_net_income_to_assets_v2": float(index),
                }
            )
            label_index.append((trade_date, f"SH{code[:6]}"))
            label_values.append(float(index))
    labels = pd.Series(
        label_values,
        index=pd.MultiIndex.from_tuples(label_index, names=["datetime", "instrument"]),
    )
    positive = CandidateSpec(
        "fundamental_net_income_to_assets_v2",
        "a / b",
        1,
        "positive rationale",
        3,
        3,
    )
    negative = CandidateSpec(
        "fundamental_net_income_to_assets_v2",
        "a / b",
        -1,
        "negative rationale",
        3,
        3,
    )
    panel = pd.DataFrame(panel_rows)
    assert evaluate_discovery(
        positive, panel, labels, start="2017-01-01", end="2018-12-31", minimum=252
    ).direction_pass
    rejected = evaluate_discovery(
        negative, panel, labels, start="2017-01-01", end="2018-12-31", minimum=252
    )
    assert not rejected.direction_pass
    assert rejected.mean_rank_ic > 0


def test_immutable_json_reuses_only_identical_content(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    _, first_sha, first_reused = write_json_once(path, {"status": "PASS"})
    _, second_sha, second_reused = write_json_once(path, {"status": "PASS"})
    assert first_sha == second_sha
    assert not first_reused
    assert second_reused
    with pytest.raises(RuntimeError, match="immutable JSON differs"):
        write_json_once(path, {"status": "FAIL"})
