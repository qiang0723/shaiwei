from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shaiwei.research.star50_residual.compute import CANDIDATES
from shaiwei.research.star50_residual_effect.contract import (
    EffectProtocol,
    ResidualEffectError,
    _validate,
    verify_pushed_clean_state,
)
from shaiwei.research.star50_residual_effect.data import EffectInputs, build_labels, neutralize
from shaiwei.research.star50_residual_effect.evidence import append_once
from shaiwei.research.star50_residual_effect.judge import safe_judge_candidates
from shaiwei.research.star50_residual_effect.metrics import _between, blend_signal


def test_effect_protocol_is_fixed_and_does_not_impersonate_g1() -> None:
    protocol = EffectProtocol.load().document
    assert len(protocol["candidates"]) == 3
    assert len(protocol["evaluation"]["oos_windows"]) == 6
    assert protocol["evaluation"]["formal_g1_v1_status"].startswith("NOT_RUN_")
    assert protocol["scope"]["model_training_authorized"] is False
    assert protocol["scope"]["deepseek_or_external_api_authorized"] is False


def test_protocol_rejects_g1_name_laundering() -> None:
    document = deepcopy(EffectProtocol.load().document)
    document["evaluation"]["formal_g1_v1_status"] = "PASS"
    with pytest.raises(ResidualEffectError, match="impersonate"):
        _validate(document)


def _label_fixture() -> EffectInputs:
    calendar = tuple(pd.bdate_range("2024-01-02", periods=13).strftime("%Y%m%d"))
    members = pd.DataFrame(
        {
            "trade_date": calendar,
            "ts_code": ["688001.SH"] * len(calendar),
        }
    )
    market = members.copy()
    market["open"] = np.arange(100.0, 100.0 + len(calendar))
    return EffectInputs(
        members=members,
        market=market,
        benchmark=pd.DataFrame(),
        calendar=calendar,
        discovery_reference=pd.DataFrame(),
        predictions={},
    )


def test_label_uses_next_open_and_t_plus_11_open() -> None:
    protocol = EffectProtocol.load()
    labels = build_labels(_label_fixture(), protocol)
    first = labels.iloc[0]
    assert first["entry_date"] == _label_fixture().calendar[1]
    assert first["exit_date"] == _label_fixture().calendar[11]
    assert np.isclose(first["label"], 111.0 / 101.0 - 1.0)
    assert labels.iloc[-1]["label"] != labels.iloc[-1]["label"]


def test_label_shift_sentinel_changes_only_eligible_prior_signal() -> None:
    protocol = EffectProtocol.load()
    inputs = _label_fixture()
    original = build_labels(inputs, protocol).set_index("trade_date")["label"]
    altered_market = inputs.market.copy()
    altered_market.loc[altered_market["trade_date"].eq(inputs.calendar[11]), "open"] *= 2
    altered = build_labels(
        EffectInputs(
            members=inputs.members,
            market=altered_market,
            benchmark=inputs.benchmark,
            calendar=inputs.calendar,
            discovery_reference=inputs.discovery_reference,
            predictions=inputs.predictions,
        ),
        protocol,
    ).set_index("trade_date")["label"]
    changed = original.ne(altered) & ~(original.isna() & altered.isna())
    assert changed[inputs.calendar[0]]
    assert int(changed.sum()) == 1


def test_neutralization_is_deterministic_and_uses_optional_baseline() -> None:
    codes = [f"688{i:03d}.SH" for i in range(1, 41)]
    features = pd.DataFrame({"trade_date": ["20240102"] * 40, "ts_code": codes})
    members = pd.DataFrame(
        {
            "trade_date": ["20240102"] * 40,
            "ts_code": codes,
            "industry": ["A"] * 20 + ["B"] * 20,
            "total_mv": np.linspace(100, 500, 40),
        }
    )
    predictions = features.copy()
    predictions["baseline_score"] = np.linspace(-1, 1, 40)
    noise = np.sin(np.arange(40))
    for offset, candidate in enumerate(CANDIDATES):
        features[candidate] = np.log(members["total_mv"]) + predictions["baseline_score"] + noise * (
            offset + 1
        )
    first = neutralize(features, members, predictions=predictions)
    second = neutralize(features, members, predictions=predictions)
    assert first.equals(second)
    assert len(first) == 40
    assert np.isfinite(first[list(CANDIDATES)].to_numpy()).all()


def test_blend_uses_cross_sectional_percentile_ranks() -> None:
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2024-01-02")], ["SH688001", "SH688002", "SH688003"]],
        names=["datetime", "instrument"],
    )
    baseline = pd.Series([1.0, 2.0, 3.0], index=index)
    factor = pd.Series([3.0, 2.0, 1.0], index=index)
    blended = blend_signal(baseline, factor, factor_weight=0.1)
    assert np.allclose(blended.to_numpy(), [0.4, 2 / 3, 14 / 15])


def test_between_accepts_signal_multi_index_and_daily_ic_index() -> None:
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    signal_index = pd.MultiIndex.from_product(
        [dates, ["SH688001"]], names=["datetime", "instrument"]
    )
    signal = pd.Series([1.0, 2.0, 3.0], index=signal_index)
    daily_ic = pd.Series([0.1, 0.2, 0.3], index=pd.DatetimeIndex(dates, name=None))

    assert _between(signal, "2024-01-03", "2024-01-04").tolist() == [2.0, 3.0]
    assert _between(daily_ic, "2024-01-03", "2024-01-04").tolist() == [0.2, 0.3]


def test_between_rejects_multi_index_without_datetime_contract() -> None:
    index = pd.MultiIndex.from_product(
        [["2024-01-02"], ["SH688001"]], names=["date", "instrument"]
    )
    with pytest.raises(ResidualEffectError, match="lacks datetime level"):
        _between(pd.Series([1.0], index=index), "2024-01-01", "2024-01-31")


def test_direction_reject_does_not_claim_oos_read() -> None:
    protocol = EffectProtocol.load().document
    directions = {
        candidate: {"mean_rank_ic": -0.01, "observation_count": 300, "direction_pass": False}
        for candidate in CANDIDATES
    }
    decisions = safe_judge_candidates([], directions, protocol, {"pit": True, "shift": True})
    assert len(decisions) == 3
    assert all(row["oos_effect_read"] is False for row in decisions)
    assert all(row["adapted_gate_decision"] == "REJECT_DIRECTION" for row in decisions)


def test_append_only_ledger_is_idempotent_and_conflict_closed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.csv"
    fields = ("id", "value")
    path.write_text("id,value\n", encoding="utf-8")
    assert append_once(path, fields, {"id": "one", "value": "A"}, "one") is False
    assert append_once(path, fields, {"id": "one", "value": "A"}, "one") is True
    assert path.read_text(encoding="utf-8").splitlines() == ["id,value", "one,A"]
    with pytest.raises(ResidualEffectError, match="conflict"):
        append_once(path, fields, {"id": "one", "value": "B"}, "one")


def test_compose_effect_service_is_isolated_and_has_narrow_writes() -> None:
    import yaml

    service = yaml.safe_load(Path("compose.research.yaml").read_text())["services"][
        "m4-star50-residual-effect"
    ]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["build"]["args"]["SHAIWEI_RELEASE_GIT_HEAD"] == (
        "${SHAIWEI_M4_EFFECT_RELEASE_GIT_HEAD:-}"
    )
    writable = [volume["target"] for volume in service["volumes"] if not volume["read_only"]]
    assert writable == [
        "/workspace/data/research/m4/m4-star50-benchmark-residual-effect-v1",
        "/workspace/ledger/m4_star50_residual_effect_runs.csv",
        "/workspace/ledger/m4_star50_residual_effect_decisions.csv",
    ]


def test_container_release_uses_embedded_manifest_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    import shaiwei.research.star50_residual_effect.contract as contract

    head = "a" * 40
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", "/opt/shaiwei/release-manifest.json")
    monkeypatch.setattr(contract, "code_snapshot_sha256", lambda: "b" * 64)
    monkeypatch.setattr(contract, "git_head", lambda: head)
    release = SimpleNamespace(document={"implementation_git_head": head})
    assert verify_pushed_clean_state(release) == head
