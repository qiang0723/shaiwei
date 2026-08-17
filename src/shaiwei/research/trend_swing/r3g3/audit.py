"""Independent raw-artifact checks for the R3G-3 aggregate diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

import numpy as np

from shaiwei.research.trend_swing.r3g3.contract import DiagnosticProtocol, SCENARIOS
from shaiwei.research.trend_swing.r3g3.evidence import (
    R3G3Error,
    canonical_json,
    file_manifest,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.r3g3.reader import load_inputs


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G3Error(f"R3G-3 audit input is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G3Error(f"R3G-3 audit input is not a mapping: {path.name}")
    return value


def _point_checks(source: Any, report: dict[str, Any]) -> dict[str, bool]:
    trades, orders, nav = source.trades, source.orders, source.nav
    closed = trades.loc[trades["closed_trade"].astype(bool)]
    buy_gross = float(trades.loc[trades["side"].eq("BUY"), "gross_notional"].sum())
    sell_gross = float(trades.loc[trades["side"].eq("SELL"), "gross_notional"].sum())
    fees = float(trades["fees"].sum())
    economics, participation, funnel = (
        report["trade_economics"], report["participation"], report["orders"]
    )
    scenario_values = report["cost_scenarios"]["pooled_net_return"]
    return {
        "closed_trade_count": int(len(closed)) == economics["closed_trade_count"],
        "stored_net_pnl": np.isclose(
            float(closed["closed_trade_pnl"].sum()), economics["net_pnl_rmb"], rtol=0, atol=1e-6
        ),
        "gross_pnl": np.isclose(
            sell_gross - buy_gross, economics["gross_pnl_before_fees_rmb"], rtol=0, atol=1e-6
        ),
        "fees": np.isclose(fees, economics["fees_rmb"], rtol=0, atol=1e-6),
        "mean_cash": np.isclose(
            float(nav["cash_ratio"].mean()), participation["cash_ratio_all_days"]["mean"],
            rtol=0, atol=1e-12,
        ),
        "invested_days": int(nav["position_count"].gt(0).sum()) == participation["invested_day_count"],
        "order_count": len(orders) == funnel["total_order_count"],
        "exit_group_pnl": np.isclose(
            sum(row["net_pnl_rmb"] for row in economics["terminal_exit_groups"]),
            economics["net_pnl_rmb"], rtol=0, atol=1e-6,
        ),
        "cost_summaries": all(
            np.isclose(
                float(source.summaries[scenario]["pooled_net_return"]),
                float(scenario_values[scenario]), rtol=0, atol=1e-15,
            )
            for scenario in SCENARIOS
        ),
    }


def audit(
    *, protocol_path: Path, input_root: Path, diagnostic_root: Path, audit_root: Path
) -> dict[str, Any]:
    if any(audit_root.iterdir()) if audit_root.exists() else False:
        raise R3G3Error("R3G-3 audit output is not empty")
    protocol = DiagnosticProtocol.load(protocol_path)
    first = _json(diagnostic_root / "first_pass/diagnostic.json")
    replay = _json(diagnostic_root / "replay/diagnostic.json")
    final = _json(diagnostic_root / "report.json")
    manifest = _json(diagnostic_root / "manifest.json")
    sources = load_inputs(protocol, input_root)
    point_checks = {
        role: _point_checks(sources.points[role], final["points"][role])
        for role, _ in protocol.points
    }
    serialized = canonical_json(final).decode("utf-8")
    checks = {
        "first_pass_equals_replay": canonical_json(first) == canonical_json(replay),
        "final_equals_internal_pass": canonical_json(final) == canonical_json(first),
        "output_manifest": manifest == file_manifest(diagnostic_root),
        "protocol_identity": final.get("protocol_sha256") == protocol.sha256,
        "parent_verdict_unchanged": final.get("parent_verdict") == "REJECT_TS_V5_R3G2_DISCOVERY",
        "zero_new_effect_attempt": final.get("strategy_effect_attempt_increment") == 0,
        "no_holdout_or_2026_output": (
            "holdout" not in serialized.lower()
            and final.get("window") == {"start": "20210104", "end": "20231229", "role": "discovery"}
        ),
        "no_security_or_industry_labels": not re.search(
            r"\b\d{6}\.(?:SH|SZ|BJ)\b|\"ts_code\"|\"industry\"", serialized
        ),
        "all_point_arithmetic": all(all(rows.values()) for rows in point_checks.values()),
        "production_unchanged": final.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        raise R3G3Error("R3G-3 independent audit failed")
    document = {
        "schema_version": "ts-v5-r3g3-discovery-diagnostic-audit-v1",
        "protocol_sha256": protocol.sha256,
        "diagnostic_report_sha256": sha256_file(diagnostic_root / "report.json"),
        "diagnostic_manifest_sha256": sha256_file(diagnostic_root / "manifest.json"),
        "checks": checks,
        "point_arithmetic_checks": point_checks,
        "independent_audit": "PASS",
        "strategy_effect_attempt_increment": 0,
        "parent_verdict": "REJECT_TS_V5_R3G2_DISCOVERY",
        "production_authorization": "none",
    }
    digest = write_once_json(audit_root / "audit.json", document)
    return {**document, "audit_sha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(**vars(args)), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
