from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest
import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.r3g3.audit import _point_checks
from shaiwei.research.trend_swing.r3g3.compute import compute_diagnostic
from shaiwei.research.trend_swing.r3g3.contract import DiagnosticProtocol
from shaiwei.research.trend_swing.r3g3.evidence import R3G3Error, canonical_json
from shaiwei.research.trend_swing.r3g3.reader import DiagnosticInputs, PointInputs
from shaiwei.research.trend_swing.r3g3 import run as run_module
from shaiwei.research.trend_swing.r3g3 import audit as audit_module


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/ts_v5_r3g3_discovery_diagnostic_v1.yaml"
COMPOSE = ROOT / "compose.ts-v5-r3g3-diagnostic.yaml"


def _nav() -> pd.DataFrame:
    dates = ["20210104", "20210105", "20210106", "20210107", "20210108", "20210111"]
    rows = []
    for index, day in enumerate(dates):
        positions = 0 if index == 5 else 1 + int(index == 1)
        gross = 0.0 if positions == 0 else 0.02 + 0.01 * int(index == 1)
        rows.append(
            {
                "trade_date": day,
                "nav": 500_000.0 - index * 100.0,
                "daily_return": -0.0002,
                "benchmark_return": -0.001,
                "active_return": 0.0008,
                "cash_ratio": 1.0 - gross,
                "gross_weight": gross,
                "maximum_security_weight": gross,
                "maximum_industry_weight": gross,
                "position_count": positions,
                "corporate_action_overlap_count": 0,
            }
        )
    return pd.DataFrame(rows)


def _orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["20210104", "000001.SZ", "BUY", 1, "FIRST_ENTRY", "FILLED", 10_000.0, False],
            ["20210105", "000001.SZ", "BUY", 2, "SECOND_BATCH", "FILLED", 5_000.0, False],
            ["20210105", "000002.SZ", "BUY", 1, "FIRST_ENTRY", "FILLED", 10_000.0, False],
            ["20210105", "000003.SZ", "BUY", 1, "OPEN_NOT_BUYABLE", "REJECTED", 0.0, False],
            ["20210106", "000001.SZ", "SELL", 0, "TAKE_PROFIT", "FILLED", 14_800.0, False],
            ["20210111", "000002.SZ", "SELL", 0, "TIME_EXIT", "FILLED", 9_500.0, False],
        ],
        columns=[
            "trade_date", "ts_code", "side", "batch", "reason", "status", "filled_notional",
            "capacity_limited",
        ],
    )


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["20210104", "e1", "000001.SZ", "I1", "BUY", 1, "ENTRY", 10_000.0, 5.0, False, 0.0],
            ["20210105", "e1", "000001.SZ", "I1", "BUY", 2, "ENTRY", 5_000.0, 5.0, False, 0.0],
            ["20210106", "e1", "000001.SZ", "I1", "SELL", 0, "TAKE_PROFIT", 14_800.0, 6.0, True, -216.0],
            ["20210105", "e2", "000002.SZ", "I2", "BUY", 1, "ENTRY", 10_000.0, 5.0, False, 0.0],
            ["20210111", "e2", "000002.SZ", "I2", "SELL", 0, "TIME_EXIT", 9_500.0, 6.0, True, -511.0],
        ],
        columns=[
            "trade_date", "episode_id", "ts_code", "industry", "side", "batch", "reason",
            "gross_notional", "fees", "closed_trade", "closed_trade_pnl",
        ],
    )


def _inputs() -> DiagnosticInputs:
    summaries = {
        "base_1x": {"pooled_net_return": -0.001},
        "all_costs_2x": {"pooled_net_return": -0.002},
        "base_plus_10bp_slippage_each_side": {"pooled_net_return": -0.003},
    }
    point = PointInputs(_nav(), _orders(), _trades(), summaries)
    return DiagnosticInputs(
        identity={"first_pass_bundle_sha256": "a" * 64},
        points={role: point for role in ("primary", "confirmation_neighbour", "tolerance_neighbour")},
    )


def test_pure_diagnostic_reconciles_loss_and_keeps_rows_anonymous() -> None:
    protocol = DiagnosticProtocol.load(PROTOCOL)
    report = compute_diagnostic(protocol, _inputs())
    primary = report["points"]["primary"]
    economics = primary["trade_economics"]
    assert economics["gross_pnl_before_fees_rmb"] == pytest.approx(-700.0)
    assert economics["fees_rmb"] == pytest.approx(27.0)
    assert economics["net_pnl_rmb"] == pytest.approx(-727.0)
    assert report["observed_bottlenecks"][0]["finding"] == (
        "NEGATIVE_PRE_FEE_TRADE_ECONOMICS"
    )
    assert primary["orders"]["first_batch_fill_rate"] == pytest.approx(2 / 3)
    assert primary["orders"]["second_batch_entry_notional_share"] == pytest.approx(0.2)
    serialized = canonical_json(report).decode("utf-8")
    assert "000001.SZ" not in serialized and '"ts_code"' not in serialized
    assert '"industry"' not in serialized


def test_frozen_exit_and_holding_groups_cover_net_pnl_once() -> None:
    report = compute_diagnostic(DiagnosticProtocol.load(PROTOCOL), _inputs())
    economics = report["points"]["primary"]["trade_economics"]
    assert sum(row["closed_trade_count"] for row in economics["terminal_exit_groups"]) == 2
    assert sum(row["net_pnl_rmb"] for row in economics["terminal_exit_groups"]) == pytest.approx(
        -727.0
    )
    assert {row["group"] for row in economics["holding_duration_groups"]} == {
        "D01_05",
    }


def test_independent_point_arithmetic_recomputes_all_critical_metrics() -> None:
    inputs, protocol = _inputs(), DiagnosticProtocol.load(PROTOCOL)
    report = compute_diagnostic(protocol, inputs)
    checks = _point_checks(inputs.points["primary"], report["points"]["primary"])
    assert checks and all(checks.values())


def test_episode_pnl_tamper_fails_closed() -> None:
    inputs, protocol = _inputs(), DiagnosticProtocol.load(PROTOCOL)
    tampered = inputs.points["primary"].trades.copy()
    tampered.loc[tampered["closed_trade"].astype(bool), "closed_trade_pnl"] = 1.0
    points = dict(inputs.points)
    points["primary"] = PointInputs(
        inputs.points["primary"].nav, inputs.points["primary"].orders, tampered,
        inputs.points["primary"].summaries,
    )
    with pytest.raises(R3G3Error, match="episode PnL"):
        compute_diagnostic(protocol, DiagnosticInputs(inputs.identity, points))


def test_docker_boundary_mounts_only_discovery_and_dedicated_outputs() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    services = document["services"]
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    for name in ("ts-v5-r3g3-diagnostic-runner", "ts-v5-r3g3-diagnostic-auditor"):
        sources = [row["source"] for row in services[name]["volumes"]]
        assert all("/replay" not in source and "/holdout" not in source for source in sources)
        assert any(str(source).endswith("first_pass/discovery") for source in sources)
    assert "compose.ts-v5-r3g3-diagnostic.yaml" in CONTROLLED_FILES
    assert "compose.ts-v5-r3g3-diagnostic.yaml" in (ROOT / "Dockerfile").read_text()


def test_r3g3_modules_remain_small_and_role_specific() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/r3g3"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))


def test_runner_cli_maps_public_names_to_internal_paths(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"verdict": "fixture"}

    monkeypatch.setattr(run_module, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r3g3-run",
            "--protocol", str(tmp_path / "protocol.yaml"),
            "--recovery-scope", str(tmp_path / "recovery.yaml"),
            "--input-root", str(tmp_path / "inputs"),
            "--output-root", str(tmp_path / "outputs"),
        ],
    )
    assert run_module.main() == 0
    assert captured == {
        "protocol_path": tmp_path / "protocol.yaml",
        "recovery_scope_path": tmp_path / "recovery.yaml",
        "input_root": tmp_path / "inputs",
        "output_root": tmp_path / "outputs",
    }
    assert '"verdict": "fixture"' in capsys.readouterr().out


def test_auditor_cli_maps_public_names_to_internal_paths(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    def fake_audit(**kwargs):
        captured.update(kwargs)
        return {"independent_audit": "fixture"}

    monkeypatch.setattr(audit_module, "audit", fake_audit)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r3g3-audit",
            "--protocol", str(tmp_path / "protocol.yaml"),
            "--recovery-scope", str(tmp_path / "recovery.yaml"),
            "--input-root", str(tmp_path / "inputs"),
            "--diagnostic-root", str(tmp_path / "diagnostic"),
            "--audit-root", str(tmp_path / "audit"),
        ],
    )
    assert audit_module.main() == 0
    assert captured == {
        "protocol_path": tmp_path / "protocol.yaml",
        "recovery_scope_path": tmp_path / "recovery.yaml",
        "input_root": tmp_path / "inputs",
        "diagnostic_root": tmp_path / "diagnostic",
        "audit_root": tmp_path / "audit",
    }
    assert '"independent_audit": "fixture"' in capsys.readouterr().out
