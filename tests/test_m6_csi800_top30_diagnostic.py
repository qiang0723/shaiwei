from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research.model_attribution.effect_execution import scheduled_top30
from shaiwei.research.top30_diagnostic import release as release_module
from shaiwei.research.top30_diagnostic.audit import classify_exact
from shaiwei.research.top30_diagnostic.contract import (
    ACTION,
    Approval,
    Protocol,
    ReleaseScope,
)
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, exact_diff, exact_rows
from shaiwei.research.top30_diagnostic.fixture import run_fixture
from shaiwei.research.top30_diagnostic.runner import run


def _report(offset: float = 0.0) -> pd.DataFrame:
    dates = pd.to_datetime(["2019-01-02", "2019-01-03"])
    return pd.DataFrame(
        {
            "gross_return": [0.001 + offset, 0.002 + offset],
            "benchmark_return": [0.0001, 0.0002],
            "recorded_cost": [0.00003, 0.00004],
            "turnover": [0.01, 0.02],
        },
        index=dates,
    )


def _scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    commit = "1" * 40
    monkeypatch.setattr(release_module, "_git", lambda _name: commit)
    document = release_module.build_scope(
        original_image_id="sha256:" + "2" * 64,
        current_image_id="sha256:" + "3" * 64,
        original_manifest_sha256="4" * 64,
        current_manifest_sha256="5" * 64,
        platform="linux/arm64",
    )
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(document), encoding="utf-8")
    approval = {
        "schema_version": "m6-top30-compatibility-diagnostic-approval-v1",
        "diagnostic_scope_sha256": document["diagnostic_scope_sha256"],
        "action": ACTION,
        "approved_at": "2026-08-07T13:00:00+08:00",
        "consumed": False,
        "real_qlib_read_authorized": True,
        "sealed_prediction_or_report_read_authorized": True,
        "failed_release_evidence_read_authorized": True,
        "real_top30_diagnostic_backtest_authorized": True,
        "real_top20_read_or_backtest_authorized": False,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    return release_path, approval_path


def _case(root: Path) -> None:
    prefix = root / "first_pass/W1"
    (prefix / "test_predictions").mkdir(parents=True)
    (prefix / "backtest").mkdir(parents=True)
    (prefix / "top30").mkdir(parents=True)
    dates = pd.to_datetime(["2019-01-02", "2019-01-03"])
    prediction = pd.DataFrame(
        [
            {"datetime": day, "instrument": f"SH{index:06d}", "score": float(40 - index)}
            for day in dates
            for index in range(35)
        ]
    )
    prediction.to_parquet(prefix / "test_predictions/clean_lgbm_control_v1.parquet", index=False)
    report = _report().rename_axis("datetime").reset_index()
    report.to_parquet(prefix / "backtest/clean_lgbm_control_v1.parquet", index=False)
    series = prediction.set_index(["datetime", "instrument"])["score"].sort_index()
    schedule = scheduled_top30(series, rebalance_days=10)
    (prefix / "top30/clean_lgbm_control_v1.json").write_text(
        json.dumps(schedule), encoding="utf-8"
    )


def test_protocol_and_release_scope_are_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = Protocol.load()
    release_path, approval_path = _scope(tmp_path, monkeypatch)
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    assert release.scope["execution"]["total_top30_backtest_count"] == 6
    assert release.scope["execution"]["top20_backtest_count"] == 0
    assert approval.document["real_top20_read_or_backtest_authorized"] is False
    changed = json.loads(release_path.read_text())
    changed["scope"]["execution"]["top20_backtest_count"] = 1
    release_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(DiagnosticError, match="self hash"):
        ReleaseScope.load(release_path, protocol)


def test_wrapper_copy_preserves_directory_traversal_for_non_root() -> None:
    dockerfile = Path("Dockerfile.m6-top30-diagnostic").read_text(encoding="utf-8")
    copy_line = next(line for line in dockerfile.splitlines() if "top30_diagnostic" in line and line.startswith("COPY"))
    assert "--chmod" not in copy_line


def test_exact_encoding_has_no_tolerance() -> None:
    baseline, changed = exact_rows(_report()), exact_rows(_report(1e-15))
    result = exact_diff(baseline, changed)
    assert not result["exact_equal"]
    assert result["mismatch_cell_count"] == 2
    assert result["first_mismatch"]["field"] == "gross_return"


def test_all_frozen_classifications_are_covered() -> None:
    report = run_fixture()
    assert report["fixture"] == "PASS"
    assert report["classification_case_count"] == 6
    assert report["real_top30_backtest_count"] == 0


def test_mixed_pattern_is_not_forced_into_a_causal_label() -> None:
    canonical = exact_rows(_report())
    one, two = exact_rows(_report(1e-6)), exact_rows(_report(2e-6))
    original = {"adapters": {"original_execution": {
        "replay_1": {"rows": one}, "replay_2": {"rows": one}
    }}}
    current = {"adapters": {
        "original_execution": {"replay_1": {"rows": two}, "replay_2": {"rows": two}},
        "new_execution": {"replay_1": {"rows": one}, "replay_2": {"rows": one}},
    }}
    assert classify_exact(canonical, original, current)[0] == "MIXED_UNRESOLVED"


@pytest.mark.parametrize("lane,expected_count", [("original", 2), ("current", 4)])
def test_runner_uses_only_frozen_top30_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane: str,
    expected_count: int,
) -> None:
    release_path, approval_path = _scope(tmp_path, monkeypatch)
    m6_root = tmp_path / "m6-effect"
    _case(m6_root)
    failed_root = tmp_path / "failed-effect"
    failed_root.mkdir()
    provider = tmp_path / "qlib"
    provider.mkdir()
    calls = {"count": 0}

    def fake_backtest(_signal: pd.Series) -> pd.DataFrame:
        calls["count"] += 1
        return _report()

    result = run(
        lane=lane,
        protocol_path=Path("config/m6_csi800_top30_compatibility_diagnostic_v1.yaml"),
        release_path=release_path,
        approval_path=approval_path,
        provider_root=provider,
        m6_effect_root=m6_root,
        failed_effect_root=failed_root,
        output_root=tmp_path / f"output-{lane}",
        identity_verifier=lambda *_args: {"fixture": True},
        runtime_verifier=lambda *_args: {"fixture": "runtime"},
        initializer=lambda _path: None,
        original_factory=lambda _protocol: fake_backtest,
        new_factory=lambda _protocol: fake_backtest,
    )
    bundle = json.loads((tmp_path / f"output-{lane}/bundle.json").read_text())
    assert result["lane"] == lane
    assert calls["count"] == expected_count
    assert bundle["top30_backtest_count"] == expected_count
    assert bundle["top20_backtest_count"] == 0
    assert bundle["research_attempt_increment"] == 0


def test_runner_failure_never_marks_top20(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path, approval_path = _scope(tmp_path, monkeypatch)
    m6_root = tmp_path / "m6-effect"
    _case(m6_root)
    failed_root = tmp_path / "failed-effect"
    failed_root.mkdir()
    provider = tmp_path / "qlib"
    provider.mkdir()

    def broken(_signal: pd.Series) -> pd.DataFrame:
        raise RuntimeError("synthetic failure")

    output = tmp_path / "output"
    with pytest.raises(RuntimeError, match="synthetic failure"):
        run(
            lane="original",
            protocol_path=Path("config/m6_csi800_top30_compatibility_diagnostic_v1.yaml"),
            release_path=release_path,
            approval_path=approval_path,
            provider_root=provider,
            m6_effect_root=m6_root,
            failed_effect_root=failed_root,
            output_root=output,
            identity_verifier=lambda *_args: {},
            runtime_verifier=lambda *_args: {},
            initializer=lambda _path: None,
            original_factory=lambda _protocol: broken,
        )
    failure = json.loads((output / "failure.json").read_text())
    assert failure["top20_effect_started"] is False
    assert failure["portfolio_attempts_consumed"] == 0
    assert failure["same_release_retry_authorized"] is False
