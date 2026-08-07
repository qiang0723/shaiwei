from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shaiwei.research.model_attribution.contract import (
    ProtocolBundle as M6ProtocolBundle,
    canonical_sha256,
)
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.execution import scheduled_topk
from shaiwei.research.topk_conversion.real_contract import RealProtocol
from shaiwei.research.topk_conversion.real_execution import build_real_case
from shaiwei.research.topk_conversion.real_fixture import execute_fixture
from shaiwei.research.topk_conversion.real_inputs import _validate_manifest
from shaiwei.research.topk_conversion.schema import ARMS, WINDOWS


def _prediction(start: str, arm_index: int) -> pd.Series:
    dates = pd.bdate_range(start, periods=31)
    names = [f"SYN{index:03d}" for index in range(40)]
    index = pd.MultiIndex.from_product([dates, names], names=["datetime", "instrument"])
    step = np.tile(np.arange(40, dtype=float), len(dates))
    values = step + arm_index * np.sin(np.arange(len(index), dtype=float) / 11.0)
    return pd.Series(values, index=index, name="score")


def _fake_report(signal: pd.Series, *, start: str, topk: int) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=20)
    step = np.arange(len(dates), dtype=float)
    arm_shift = float(signal.iloc[0]) * 1e-7
    return pd.DataFrame(
        {
            "gross_return": 0.0002 + arm_shift + (30 - topk) * 1e-6 + np.sin(step) * 1e-5,
            "benchmark_return": 0.0001 + np.cos(step) * 1e-6,
            "recorded_cost": np.full(len(dates), 0.00003),
            "turnover": np.full(len(dates), 0.01 + (30 - topk) * 1e-5),
        },
        index=dates,
    )


def _sealed() -> dict:
    windows = {row["name"]: row for row in M6ProtocolBundle.load().result["windows"]}
    predictions = {
        window: {
            arm: _prediction(str(windows[window]["test"][0]), arm_index)
            for arm_index, arm in enumerate(ARMS)
        }
        for window in WINDOWS
    }
    stress_predictions = {
        arm: _prediction("2026-01-01", arm_index) for arm_index, arm in enumerate(ARMS)
    }
    return {
        "predictions": predictions,
        "reports": {
            window: {
                arm: _fake_report(
                    predictions[window][arm], start=str(windows[window]["test"][0]), topk=30
                )
                for arm in ARMS
            }
            for window in WINDOWS
        },
        "top30": {
            window: {
                arm: scheduled_topk(predictions[window][arm], topk=30, rebalance_days=10)
                for arm in ARMS
            }
            for window in WINDOWS
        },
        "stress_predictions": stress_predictions,
        "stress_reports": {
            arm: _fake_report(stress_predictions[arm], start="2026-01-01", topk=30)
            for arm in ARMS
        },
    }


def test_real_case_replays_every_top30_before_top20_and_keeps_all_schedules() -> None:
    calls: list[int] = []
    started: list[bool] = []

    def backtester(signal, *, start, end, protocol, topk):
        del end, protocol
        calls.append(topk)
        return _fake_report(signal, start=start, topk=topk)

    case = build_real_case(
        _sealed(),
        RealProtocol.load(),
        backtester=backtester,
        on_top20_start=lambda: started.append(True),
    )
    assert calls == [30] * 21 + [20] * 21
    assert started == [True]
    for topk in ("30", "20"):
        for window in WINDOWS:
            schedules = case["scheduled_names"][topk][window]
            assert all(len(value) == 4 for value in schedules.values())
    assert set(case["stress_reports"]["20"]) == {
        "microcap_crash_2024",
        "volume_price_drawdown_2026h1",
    }


def test_top30_mismatch_blocks_before_attempt_consumption() -> None:
    sealed = deepcopy(_sealed())
    sealed["reports"]["W1"][ARMS[0]].iloc[0, 0] += 0.1
    calls: list[int] = []
    started: list[bool] = []

    def backtester(signal, *, start, end, protocol, topk):
        del end, protocol
        calls.append(topk)
        return _fake_report(signal, start=start, topk=topk)

    with pytest.raises(ConversionError, match="Top30 canonical report differs"):
        build_real_case(
            sealed,
            RealProtocol.load(),
            backtester=backtester,
            on_top20_start=lambda: started.append(True),
        )
    assert calls == [30]
    assert started == []


def test_pure_synthetic_real_release_runner_and_independent_audit(tmp_path: Path) -> None:
    result = execute_fixture(tmp_path)
    assert result["real_data_read"] is False
    assert result["qlib_read"] is False
    assert result["real_backtest_count"] == 0
    assert result["runner"]["strategy_effective"] == "PENDING_INDEPENDENT_AUDIT"
    assert result["auditor"]["independent_audit"] == "PASS"
    assert result["auditor"]["strategy_effective"] == "NOT_EVALUATED_FOR_PRODUCTION"
    assert result["production_authorization"] == "none"


def test_independent_auditor_does_not_import_primary_metrics_or_execution() -> None:
    source = Path(
        "src/shaiwei/research/topk_conversion/real_audit.py"
    ).read_text(encoding="utf-8")
    assert "topk_conversion.metrics" not in source
    assert "topk_conversion.execution" not in source
    assert "topk_conversion.real_execution" not in source


def test_sealed_manifest_uses_frozen_byte_count_and_rejects_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "summary.json"
    artifact.write_bytes(b"{}\n")
    metadata = {
        "summary.json": {
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "byte_count": 3,
        }
    }
    bundle_sha = canonical_sha256(metadata)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "m6-model-attribution-pass-manifest-v1",
                "artifacts": metadata,
                "bundle_sha256": bundle_sha,
            }
        ),
        encoding="utf-8",
    )
    assert _validate_manifest(tmp_path, bundle_sha)["bundle_sha256"] == bundle_sha
    artifact.write_bytes(b"drift\n")
    with pytest.raises(ConversionError, match="artifact identity differs"):
        _validate_manifest(tmp_path, bundle_sha)


def test_new_topk_release_modules_stay_below_soft_line_limit() -> None:
    package = Path("src/shaiwei/research/topk_conversion")
    names = ("real_contract.py", "real_inputs.py", "real_execution.py", "real_run.py", "real_audit.py", "real_release.py", "real_fixture.py")
    assert all(len((package / name).read_text(encoding="utf-8").splitlines()) <= 400 for name in names)
