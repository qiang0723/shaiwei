from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from shaiwei.research.star50_residual.compute import CANDIDATES
from shaiwei.research.star50_residual_effect.audit import _candidate_decision_matches
import shaiwei.research.star50_residual_effect.closure as closure_module
from shaiwei.research.star50_residual_effect.contract import (
    EffectProtocol,
    ResidualEffectError,
    _validate,
    verify_pushed_clean_state,
)
from shaiwei.research.star50_residual_effect.closure import EvidenceClosureProtocol
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


def test_independent_audit_treats_failed_gates_as_unique_unordered_membership() -> None:
    row = {
        "direction": {"direction_pass": True},
        "gates": {"rank_ic": False, "cost": True, "turnover": False},
        "adapted_gate_decision": "REJECT",
        "failed_gates": ["turnover", "rank_ic"],
    }
    assert _candidate_decision_matches(row)

    duplicate = deepcopy(row)
    duplicate["failed_gates"] = ["turnover", "rank_ic", "rank_ic"]
    assert not _candidate_decision_matches(duplicate)

    wrong_decision = deepcopy(row)
    wrong_decision["adapted_gate_decision"] = "PASS"
    assert not _candidate_decision_matches(wrong_decision)


def test_append_only_ledger_is_idempotent_and_conflict_closed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.csv"
    fields = ("id", "value")
    path.write_text("id,value\n", encoding="utf-8")
    assert append_once(path, fields, {"id": "one", "value": "A"}, "one") is False
    assert append_once(path, fields, {"id": "one", "value": "A"}, "one") is True
    assert path.read_text(encoding="utf-8").splitlines() == ["id,value", "one,A"]
    assert not path.with_suffix(".csv.lock").exists()
    with pytest.raises(ResidualEffectError, match="conflict"):
        append_once(path, fields, {"id": "one", "value": "B"}, "one")


def test_append_only_ledger_requires_precreated_schema(tmp_path: Path) -> None:
    with pytest.raises(ResidualEffectError, match="schema differs"):
        append_once(tmp_path / "missing.csv", ("id",), {"id": "one"}, "one")


def test_append_only_ledger_works_with_read_only_parent(tmp_path: Path) -> None:
    directory = tmp_path / "ledger"
    directory.mkdir()
    path = directory / "runs.csv"
    path.write_text("id,value\n", encoding="utf-8")
    directory.chmod(0o555)
    try:
        assert append_once(path, ("id", "value"), {"id": "one", "value": "A"}, "one") is False
    finally:
        directory.chmod(0o755)
    assert path.read_text(encoding="utf-8").splitlines() == ["id,value", "one,A"]
    assert list(directory.iterdir()) == [path]


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


def test_closure_protocol_and_service_are_reuse_only() -> None:
    protocol = EvidenceClosureProtocol.load().document
    execution = protocol["execution_contract"]
    assert execution["report_reuse_branch_only"] is True
    assert execution["feature_label_rankic_portfolio_or_return_recomputation"] is False
    assert len(protocol["sealed_result_contract"]["artifacts"]) == 10

    import yaml

    service = yaml.safe_load(Path("compose.research.yaml").read_text())["services"][
        "m4-star50-residual-effect-closure"
    ]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    writable = [volume["target"] for volume in service["volumes"] if not volume["read_only"]]
    assert writable == [
        "/workspace/data/research/m4/m4-star50-benchmark-residual-effect-v1",
        "/workspace/ledger/m4_star50_residual_effect_runs.csv",
        "/workspace/ledger/m4_star50_residual_effect_decisions.csv",
    ]
    assert "shaiwei.research.star50_residual_effect.closure" in service["command"]


def test_closure_orchestrator_reuses_report_then_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {
        "run_id": "sealed-run",
        "direction_pass_count": 2,
        "adapted_gate_pass_count": 0,
        "formal_g1_v1_status": "NOT_RUN_UNIVERSE_WINDOW_DOMAIN_MISMATCH",
        "verdict": "NO_GO",
        "strategy_effective": "REJECT",
    }
    report_path = tmp_path / "result/effect_report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("{}\n", encoding="utf-8")
    (tmp_path / "ledger").mkdir()
    run_ledger = tmp_path / "ledger/runs.csv"
    decision_ledger = tmp_path / "ledger/decisions.csv"
    run_ledger.write_text("run_id\n", encoding="utf-8")
    decision_ledger.write_text("decision_id\n", encoding="utf-8")

    states = iter([("INITIAL", report), ("COMPLETED", report)])
    fake_closure = SimpleNamespace(
        sha256="c" * 64,
        document={"source_authority": {"effect_protocol_sha256": "p" * 64}},
        verify_state=lambda: next(states),
    )
    fake_protocol = SimpleNamespace(
        sha256="p" * 64,
        document={
            "identity": {
                "effect_report": "result/effect_report.json",
                "result_root": "result",
                "run_ledger": "ledger/runs.csv",
                "decision_ledger": "ledger/decisions.csv",
            }
        },
        verify_upstream=lambda: {},
    )
    fake_release = SimpleNamespace(
        document={"closure_protocol_sha256": "c" * 64, "report_reuse_only": True}
    )
    calls: list[str] = []
    monkeypatch.setattr(
        closure_module.EvidenceClosureProtocol, "load", staticmethod(lambda _: fake_closure)
    )
    monkeypatch.setattr(closure_module.EffectProtocol, "load", staticmethod(lambda _: fake_protocol))
    monkeypatch.setattr(
        closure_module.EffectRelease,
        "load",
        staticmethod(lambda *_args, **_kwargs: fake_release),
    )
    monkeypatch.setattr(closure_module, "code_bundle_sha256", lambda: "b" * 64)
    monkeypatch.setattr(closure_module, "verify_pushed_clean_state", lambda _release: "h" * 40)
    monkeypatch.setattr(
        closure_module, "project_path", lambda value: (tmp_path / value).resolve()
    )
    monkeypatch.setattr(
        closure_module,
        "append_ledgers",
        lambda *_args, **_kwargs: calls.append("append") or {"run": False, "decisions": False},
    )
    monkeypatch.setattr(closure_module, "build_manifest", lambda *_args: {"sealed": True})
    monkeypatch.setattr(
        closure_module,
        "write_json",
        lambda *_args: calls.append("manifest") or ("m" * 64, False),
    )
    monkeypatch.setattr(
        closure_module,
        "audit",
        lambda _path: calls.append("audit") or {"status": "PASS"},
    )

    result = closure_module.close_evidence(Path("effect"), Path("closure"), Path("release"))
    assert result["status"] == "PASS"
    assert result["before_state"] == "INITIAL"
    assert calls == ["append", "manifest", "audit"]


def test_container_release_uses_embedded_manifest_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    import shaiwei.research.star50_residual_effect.contract as contract

    head = "a" * 40
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", "/opt/shaiwei/release-manifest.json")
    monkeypatch.setattr(contract, "code_snapshot_sha256", lambda: "b" * 64)
    monkeypatch.setattr(contract, "git_head", lambda: head)
    release = SimpleNamespace(document={"implementation_git_head": head})
    assert verify_pushed_clean_state(release) == head
