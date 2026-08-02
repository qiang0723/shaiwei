from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.fundamental_pit_contract import FundamentalPitError, canonical_json
from shaiwei.research.fundamental_pit_recovery_contract import (
    FundamentalPitRecoveryProtocol,
    verify_predecessor,
)
from shaiwei.research.fundamental_pit_recovery_gate import build_recovery_panel


PROTOCOL = PROJECT_ROOT / "config/f1_csi800_fundamental_pit_recovery_v2.yaml"


def _protocol() -> FundamentalPitRecoveryProtocol:
    return FundamentalPitRecoveryProtocol.load(PROTOCOL)


def _row(
    name: str,
    end_date: str,
    *,
    f_ann_date: str,
    value_scale: float = 1.0,
) -> dict[str, object]:
    base: dict[str, object] = {
        "ts_code": "688001.SH",
        "f_ann_date": f_ann_date,
        "end_date": end_date,
        "report_type": "1",
        "update_flag": "1",
    }
    values = {
        "income": {
            "n_income_attr_p": 10.0 * value_scale,
            "operate_profit": 12.0 * value_scale,
            "total_revenue": 100.0 * value_scale,
        },
        "balancesheet": {
            "total_assets": 100.0 * value_scale,
            "total_liab": 40.0 * value_scale,
            "money_cap": 20.0 * value_scale,
        },
        "cashflow": {"n_cashflow_act": 8.0 * value_scale},
    }
    return {**base, **values[name]}


def _frames(*, no_common: bool = False) -> dict[str, pd.DataFrame]:
    calendar = pd.DataFrame(
        {
            "exchange": ["SSE"] * 5,
            "cal_date": ["20170428", "20170502", "20180430", "20180502", "20180531"],
            "is_open": [1, 1, 1, 1, 1],
        }
    )
    index_weight = pd.DataFrame(
        {
            "index_code": ["000906.SH"],
            "con_code": ["688001.SH"],
            "trade_date": ["20180501"],
            "weight": [100.0],
        }
    )
    periods = {
        "income": [
            _row("income", "20161231", f_ann_date="20170428"),
            _row("income", "20171231", f_ann_date="20180430", value_scale=9.0),
        ],
        "balancesheet": [
            _row("balancesheet", "20151231" if no_common else "20161231", f_ann_date="20170428")
        ],
        "cashflow": [_row("cashflow", "20161231", f_ann_date="20170428")],
    }
    frames = {"tushare.trade_cal": calendar, "tushare.index_weight": index_weight}
    for name, rows in periods.items():
        ordinary = pd.DataFrame(rows)
        frames[f"tushare.{name}"] = ordinary
        frames[f"tushare.{name}_vip"] = ordinary.iloc[:0].copy()
    return frames


def test_protocol_freezes_only_latest_common_period_recovery(tmp_path: Path):
    protocol = _protocol()
    assert protocol.document["point_in_time"]["formation_period_selection"] == (
        "latest_jointly_available_common_end_date"
    )
    assert protocol.document["scope"]["factor_results_authorized"] is False
    tampered = deepcopy(protocol.document)
    tampered["gates"]["quality_no_common_period_rows"] = 1
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(tampered), encoding="utf-8")
    with pytest.raises(FundamentalPitError, match="gates"):
        FundamentalPitRecoveryProtocol.load(path)


def test_latest_common_period_survives_one_statement_reporting_early():
    panel, diagnostics = build_recovery_panel(_protocol(), _frames())
    row = panel.loc[panel["formation_date"].eq("20180531")].iloc[0]
    assert row["end_date"] == "20161231"
    assert row["available_date"] == "20170502"
    assert row["fundamental_net_income_to_assets_v2"] == pytest.approx(0.1)
    assert row["fundamental_cash_return_on_assets_v2"] == pytest.approx(0.08)
    assert diagnostics["quality_newer_unmatched_statement_rows"] == 1
    assert diagnostics["quality_no_common_period_rows"] == 0
    assert diagnostics["constructed_mixed_component_period_rows"] == 0
    assert diagnostics["future_availability_rows"] == 0


def test_no_common_period_is_null_and_fail_closed_diagnostic():
    panel, diagnostics = build_recovery_panel(_protocol(), _frames(no_common=True))
    row = panel.loc[panel["formation_date"].eq("20180531")].iloc[0]
    assert pd.isna(row["end_date"])
    assert pd.isna(row["fundamental_net_income_to_assets_v2"])
    assert diagnostics["quality_no_common_period_rows"] == 1


def test_predecessor_verifier_rejects_rewritten_evidence(tmp_path: Path):
    feature = tmp_path / "data/old/features.parquet"
    report = tmp_path / "data/old/quality_report.json"
    manifest_path = tmp_path / "config/old_manifest.json"
    feature.parent.mkdir(parents=True)
    manifest_path.parent.mkdir(parents=True)
    feature.write_bytes(b"old-feature")
    report.write_bytes(b"old-report")
    manifest = {
        "protocol_id": "old-v1",
        "verdict": "OLD_NO_GO",
        "feature_panel": {"path": "data/old/features.parquet", "sha256": sha256_file(feature)},
        "report": {"path": "data/old/quality_report.json", "sha256": sha256_file(report)},
    }
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    protocol = SimpleNamespace(
        document={
            "predecessor": {
                "protocol_id": "old-v1",
                "verdict": "OLD_NO_GO",
                "tracked_manifest": "config/old_manifest.json",
                "tracked_manifest_sha256": sha256_file(manifest_path),
                "feature_panel_sha256": sha256_file(feature),
                "quality_report_sha256": sha256_file(report),
            }
        }
    )
    assert verify_predecessor(protocol, project_root=tmp_path)["verdict"] == "OLD_NO_GO"
    report.write_bytes(b"rewritten")
    with pytest.raises(FundamentalPitError, match="report file was rewritten"):
        verify_predecessor(protocol, project_root=tmp_path)


def test_recovery_compose_and_make_targets_are_offline_and_release_bound():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["f1-fundamental-pit-recovery"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert "env_file" not in service
    assert service["build"]["args"]["SHAIWEI_RELEASE_GIT_HEAD"] == (
        "${SHAIWEI_F1_RECOVERY_RELEASE_GIT_HEAD:-}"
    )
    writes = [volume for volume in service["volumes"] if volume.get("read_only") is False]
    assert [volume["source"] for volume in writes] == [
        "./data/research/f1_csi800_fundamental_pit_recovery_v2"
    ]
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'SHAIWEI_F1_RECOVERY_RELEASE_GIT_HEAD="$(F1_RECOVERY_RELEASE_GIT_HEAD)"' in makefile
