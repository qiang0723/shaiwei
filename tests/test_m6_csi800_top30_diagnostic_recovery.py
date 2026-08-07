from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.research.model_attribution.effect_execution import scheduled_top30
from shaiwei.research.top30_diagnostic.exact import DiagnosticError
from shaiwei.research.top30_diagnostic.recovery_contract import (
    ACTION,
    RecoveryApproval,
    RecoveryProtocol,
    RecoveryReleaseScope,
)
from shaiwei.research.top30_diagnostic import recovery_release
from shaiwei.research.top30_diagnostic.runner import run


def _scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    commit = "1" * 40
    monkeypatch.setattr(recovery_release, "_git", lambda _name: commit)
    document = recovery_release.build_scope(
        original_image_id="sha256:" + "2" * 64,
        current_image_id="sha256:" + "3" * 64,
        original_manifest_sha256="4" * 64,
        current_manifest_sha256="5" * 64,
        platform="linux/arm64",
    )
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(document), encoding="utf-8")
    approval = {
        "schema_version": "m6-top30-compatibility-diagnostic-recovery-approval-v2",
        "diagnostic_scope_sha256": document["diagnostic_scope_sha256"],
        "action": ACTION,
        "approved_at": "2026-08-07T16:00:00+08:00",
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
    prediction = pd.DataFrame([
        {"datetime": day, "instrument": f"SH{index:06d}", "score": float(40 - index)}
        for day in dates for index in range(35)
    ])
    prediction.to_parquet(prefix / "test_predictions/clean_lgbm_control_v1.parquet", index=False)
    report = pd.DataFrame({
        "datetime": dates,
        "gross_return": [0.001, 0.002],
        "benchmark_return": [0.0001, 0.0002],
        "recorded_cost": [0.00003, 0.00004],
        "turnover": [0.01, 0.02],
    })
    report.to_parquet(prefix / "backtest/clean_lgbm_control_v1.parquet", index=False)
    signal = prediction.set_index(["datetime", "instrument"])["score"].sort_index()
    schedule = scheduled_top30(signal, rebalance_days=10)
    (prefix / "top30/clean_lgbm_control_v1.json").write_text(
        json.dumps(schedule), encoding="utf-8"
    )


def test_recovery_protocol_scope_and_approval_are_versioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = RecoveryProtocol.load()
    release_path, approval_path = _scope(tmp_path, monkeypatch)
    release = RecoveryReleaseScope.load(release_path, protocol)
    approval = RecoveryApproval.load(approval_path, release)
    assert release.scope["predecessor_failure"]["top30_backtest_count"] == 0
    assert release.scope["execution"]["total_top30_backtest_count"] == 6
    assert release.scope["execution"]["top20_backtest_count"] == 0
    original_mounts = release.scope["container"]["services"]["original"]["mounts"]
    assert {
        "source": "config/m6_csi800_top30_compatibility_diagnostic_v1.yaml",
        "target": "/inputs/base-protocol.yaml",
        "mode": "ro",
    } in original_mounts
    assert approval.document["action"] == ACTION
    changed = json.loads(approval_path.read_text())
    changed["action"] = "M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_ONCE"
    approval_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(DiagnosticError, match="authority"):
        RecoveryApproval.load(approval_path, release)


def test_recovery_compose_preserves_failed_r1_and_uses_single_tmpfs_strings() -> None:
    old_compose = Path("compose.m6-top30-diagnostic.yaml")
    old_scope = Path("config/m6_csi800_top30_compatibility_diagnostic_scope_v1.json")
    assert hashlib.sha256(old_compose.read_bytes()).hexdigest() == (
        "64d619f6dddc5d9abcab19654e58d03464540dcf3bd8fbc4d78d0f21ccdcb47d"
    )
    assert hashlib.sha256(old_scope.read_bytes()).hexdigest() == (
        "2a80241ff0f8f11c23826a49cc30362b13f7fd02a2c925c21d65bbe93089de75"
    )
    document = yaml.safe_load(Path("compose.m6-top30-diagnostic-recovery.yaml").read_text())
    services = document["services"]
    expected = {
        "m6-top30-diagnostic-recovery-original": "/tmp:rw,noexec,nosuid,size=1g,mode=1777",
        "m6-top30-diagnostic-recovery-current": "/tmp:rw,noexec,nosuid,size=1g,mode=1777",
        "m6-top30-diagnostic-recovery-auditor": "/tmp:rw,noexec,nosuid,size=512m,mode=1777",
        "m6-top30-diagnostic-recovery-original-fixture": "/tmp:rw,noexec,nosuid,size=1g,mode=1777",
        "m6-top30-diagnostic-recovery-current-fixture": "/tmp:rw,noexec,nosuid,size=1g,mode=1777",
        "m6-top30-diagnostic-recovery-auditor-fixture": "/tmp:rw,noexec,nosuid,size=512m,mode=1777",
    }
    assert {name: service["tmpfs"] for name, service in services.items()} == {
        name: [value] for name, value in expected.items()
    }
    for name in expected:
        assert services[name]["network_mode"] == "none"
        assert services[name]["read_only"] is True
        assert services[name].get("volumes", []) == [] or not name.endswith("-fixture")


def test_recovery_contract_reuses_the_existing_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
        return pd.DataFrame({
            "gross_return": [0.001, 0.002],
            "benchmark_return": [0.0001, 0.0002],
            "recorded_cost": [0.00003, 0.00004],
            "turnover": [0.01, 0.02],
        }, index=pd.to_datetime(["2019-01-02", "2019-01-03"]))

    result = run(
        lane="original",
        protocol_path=Path("config/m6_csi800_top30_compatibility_diagnostic_recovery_v2.yaml"),
        release_path=release_path,
        approval_path=approval_path,
        provider_root=provider,
        m6_effect_root=m6_root,
        failed_effect_root=failed_root,
        output_root=tmp_path / "output",
        identity_verifier=lambda *_args: {"fixture": True},
        runtime_verifier=lambda *_args: {"fixture": "runtime"},
        initializer=lambda _path: None,
        original_factory=lambda _protocol: fake_backtest,
        protocol_loader=RecoveryProtocol.load,
        release_loader=RecoveryReleaseScope.load,
        approval_loader=RecoveryApproval.load,
    )
    assert calls["count"] == 2
    assert result["lane"] == "original"
    bundle = json.loads((tmp_path / "output/bundle.json").read_text())
    assert bundle["top20_backtest_count"] == 0
    assert bundle["research_attempt_increment"] == 0
