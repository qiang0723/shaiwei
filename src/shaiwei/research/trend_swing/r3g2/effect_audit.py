"""Independent artifact-only auditor for the one-shot R3G-2 effect."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping

import numpy as np
import pandas as pd

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.effect_control import EffectApproval, EffectReleaseScope
from shaiwei.research.trend_swing.r3g2.evidence import canonical_json, write_once_json


SCENARIOS = ("base_1x", "all_costs_2x", "base_plus_10bp_slippage_each_side")


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error(f"R3G-2 audit input is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G2Error(f"R3G-2 audit input is not a mapping: {path.name}")
    return value


def _bundle(files: Mapping[str, str]) -> str:
    return hashlib.sha256(canonical_json(dict(sorted(files.items())))).hexdigest()


def _manifest(root: Path) -> dict[str, Any]:
    document = _json(root / "manifest.json")
    files = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    expected = {
        "schema_version": "ts-v5-r3g2-effect-pass-manifest-v1",
        "file_count": len(files),
        "files": files,
        "bundle_sha256": _bundle(files),
    }
    if document != expected:
        raise R3G2Error("R3G-2 independent artifact manifest differs")
    return document


def _compound(values: pd.Series) -> float:
    array = pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    if array.size == 0 or not np.isfinite(array).all() or (array <= -1).any():
        raise R3G2Error("R3G-2 audited returns are invalid")
    return float(np.prod(1.0 + array) - 1.0)


def _drawdown(nav: pd.Series) -> tuple[float, int]:
    values = pd.to_numeric(nav, errors="raise").to_numpy(dtype=float)
    path = np.concatenate(([500_000.0], values))
    if values.size == 0 or not np.isfinite(path).all() or (path <= 0).any():
        raise R3G2Error("R3G-2 audited NAV is invalid")
    drawdowns = 1.0 - path / np.maximum.accumulate(path)
    longest = current = 0
    for value in drawdowns:
        current = current + 1 if value > 0 else 0
        longest = max(longest, current)
    return float(drawdowns.max()), longest


def _summary(root: Path) -> dict[str, Any]:
    nav = pd.read_parquet(root / "nav.parquet").sort_values("trade_date")
    orders, trades = pd.read_parquet(root / "orders.parquet"), pd.read_parquet(
        root / "trades.parquet"
    )
    net, comparator = _compound(nav["daily_return"]), _compound(nav["benchmark_return"])
    maximum, duration = _drawdown(nav["nav"])
    annual: dict[str, dict[str, float]] = {}
    for year, rows in nav.groupby(nav["trade_date"].astype(str).str[:4], sort=True):
        strategy, benchmark = _compound(rows["daily_return"]), _compound(
            rows["benchmark_return"]
        )
        annual[str(year)] = {
            "net_return": strategy,
            "benchmark_return": benchmark,
            "net_excess": strategy - benchmark,
        }
    closed = trades.loc[trades["closed_trade"].astype(bool)]
    pnls = closed["closed_trade_pnl"].astype(float)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    counts = closed["trade_date"].astype(str).str[:4].value_counts()
    date_index = {str(day): index for index, day in enumerate(nav["trade_date"].astype(str))}
    first_entries = (
        trades.loc[trades["side"].eq("BUY")]
        .groupby("episode_id", sort=False)["trade_date"]
        .min()
    )
    holding_days = [
        date_index[str(row.trade_date)] - date_index[str(first_entries[row.episode_id])]
        for row in closed.itertuples(index=False)
    ]
    absolute_pnl = float(pnls.abs().sum())

    def concentration(column: str) -> float | None:
        if closed.empty or absolute_pnl <= 0:
            return None
        grouped = closed.groupby(column, sort=False)["closed_trade_pnl"].sum().abs()
        return float(grouped.max() / absolute_pnl)

    return {
        "calendar_day_count": len(nav),
        "closed_trade_count": len(closed),
        "closed_trade_count_by_year": {year: int(counts.get(year, 0)) for year in annual},
        "pooled_net_return": net,
        "pooled_benchmark_return": comparator,
        "pooled_h00906_net_excess": net - comparator,
        "annual": annual,
        "maximum_drawdown": maximum,
        "maximum_drawdown_duration_days": duration,
        "win_rate": float((pnls > 0).mean()) if len(pnls) else None,
        "profit_loss_ratio": (
            float(wins.mean() / abs(losses.mean())) if not wins.empty and not losses.empty else None
        ),
        "expectancy_rmb": float(pnls.mean()) if len(pnls) else None,
        "turnover": float(trades["gross_notional"].astype(float).sum()) / 500_000.0,
        "fees_rmb": float(trades["fees"].astype(float).sum()),
        "unfilled_or_pending_order_count": int(
            orders["status"].isin(["REJECTED", "PENDING", "PARTIAL"]).sum()
        ),
        "mean_cash_ratio": float(nav["cash_ratio"].astype(float).mean()),
        "maximum_gross_weight": float(nav["gross_weight"].astype(float).max()),
        "maximum_position_count": int(nav["position_count"].astype(int).max()),
        "maximum_security_weight": float(nav["maximum_security_weight"].astype(float).max()),
        "maximum_industry_weight": float(nav["maximum_industry_weight"].astype(float).max()),
        "corporate_action_overlap_count": int(
            nav["corporate_action_overlap_count"].astype(int).max()
        ),
        "capacity_limited_order_count": int(orders["capacity_limited"].astype(bool).sum()),
        "mean_holding_days": float(np.mean(holding_days)) if holding_days else None,
        "maximum_holding_days": int(max(holding_days)) if holding_days else None,
        "maximum_absolute_trade_pnl_share": (
            float(pnls.abs().max() / absolute_pnl) if absolute_pnl > 0 else None
        ),
        "maximum_absolute_security_pnl_share": concentration("ts_code"),
        "maximum_absolute_industry_pnl_share": concentration("industry"),
        "blocked_reason": _json(root / "summary.json")["blocked_reason"],
    }


def _same(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return canonical_json(left) == canonical_json(right)


def _base_checks(summary: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, bool]:
    yearly = summary["closed_trade_count_by_year"]
    return {
        "closed_trades": int(summary["closed_trade_count"]) >= int(gate["minimum_closed_trades"]),
        "closed_trades_each_year": bool(yearly)
        and min(int(value) for value in yearly.values())
        >= int(gate["minimum_closed_trades_each_calendar_year"]),
        "positive_net": float(summary["pooled_net_return"]) > 0,
        "positive_excess": float(summary["pooled_h00906_net_excess"]) > 0,
        "maximum_drawdown": float(summary["maximum_drawdown"]) <= float(gate["maximum_drawdown"]),
        "unblocked": not summary["blocked_reason"],
    }


def _point_checks(
    summaries: Mapping[str, Mapping[str, Any]],
    gate: Mapping[str, Any],
    *,
    positive_years: int | None = None,
    annual_floor: float | None = None,
) -> dict[str, bool]:
    if tuple(summaries) != SCENARIOS:
        raise R3G2Error("R3G-2 audited cost scenario order differs")
    base = summaries[SCENARIOS[0]]
    checks = _base_checks(base, gate)
    checks["all_costs_2x"] = float(summaries[SCENARIOS[1]]["pooled_net_return"]) >= float(
        gate["all_costs_2x_pooled_net_return_minimum"]
    )
    checks["extra_10bp"] = float(summaries[SCENARIOS[2]]["pooled_net_return"]) >= float(
        gate["extra_10bp_each_side_pooled_net_return_minimum"]
    )
    if positive_years is not None:
        checks["positive_excess_years"] = sum(
            float(row["net_excess"]) > 0 for row in base["annual"].values()
        ) >= positive_years
    if annual_floor is not None:
        checks["each_year_net_minimum"] = bool(base["annual"]) and min(
            float(row["net_return"]) for row in base["annual"].values()
        ) >= annual_floor
    return checks


def _periodic_sharpe(values: pd.Series) -> float:
    array = pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    if len(array) < 252 or not np.isfinite(array).all():
        raise R3G2Error("R3G-2 audited active returns are insufficient")
    standard = float(array.std(ddof=1))
    if standard <= 0:
        raise R3G2Error("R3G-2 audited active-return variance is invalid")
    return float(array.mean() / standard)


def _dsr(nav_by_point: Mapping[str, pd.DataFrame], primary: str) -> tuple[float, dict[str, Any]]:
    try:
        sharpes = tuple(
            _periodic_sharpe(frame["active_return"]) for frame in nav_by_point.values()
        )
        trial_std = float(np.asarray(sharpes).std(ddof=1))
        normal, euler = NormalDist(), 0.5772156649015329
        expected = trial_std * (
            (1 - euler) * normal.inv_cdf(1 - 1 / 3)
            + euler * normal.inv_cdf(1 - 1 / (3 * math.e))
        )
        values = nav_by_point[primary]["active_return"].astype(float).to_numpy()
        observed = _periodic_sharpe(nav_by_point[primary]["active_return"])
        centered = values - values.mean()
        second = float(np.mean(centered**2))
        if second <= 0:
            raise R3G2Error("R3G-2 audited active-return variance is invalid")
        skew = float(np.mean(centered**3) / second**1.5)
        kurtosis = float(np.mean(centered**4) / second**2)
        denominator = 1 - skew * observed + (kurtosis - 1) / 4 * observed**2
        if not math.isfinite(denominator) or denominator <= 0:
            raise R3G2Error("R3G-2 audited DSR denominator is invalid")
        z = (observed - expected) * math.sqrt(len(values) - 1) / math.sqrt(denominator)
        return float(normal.cdf(z)), {
            "observed_periodic_sharpe": observed,
            "expected_maximum_periodic_sharpe": expected,
            "skewness": skew,
            "kurtosis": kurtosis,
            "z_score": z,
        }
    except (R3G2Error, ValueError, ArithmeticError):
        return 0.0, {"failure": "G1Error"}


def _audit_partition(root: Path, protocol: EffectProtocol, partition: str) -> dict[str, Any]:
    document = _json(root / partition / "partition_summary.json")
    summaries: dict[str, dict[str, Any]] = {}
    nav_by_point: dict[str, pd.DataFrame] = {}
    for point in protocol.selected_point_hashes:
        summaries[point] = {}
        for current in SCENARIOS:
            artifact = root / partition / point / current
            observed, recorded = _summary(artifact), _json(artifact / "summary.json")
            if not _same(observed, recorded):
                raise R3G2Error("R3G-2 independently recomputed summary differs")
            summaries[point][current] = observed
            if current == SCENARIOS[0]:
                nav_by_point[point] = pd.read_parquet(artifact / "nav.parquet")
    primary, *neighbours = protocol.selected_point_hashes
    if partition == "discovery":
        gate = protocol.document["discovery_gate"]
        checks = {
            primary: _point_checks(
                summaries[primary], gate["primary_anchor"],
                positive_years=int(
                    gate["primary_anchor"]["minimum_positive_h00906_net_excess_calendar_years"]
                ),
            )
        }
        checks.update(
            {point: _point_checks(summaries[point], gate["each_sensitivity_neighbour"])
             for point in neighbours}
        )
        probability, dsr_details = _dsr(nav_by_point, primary)
        checks[primary]["deflated_sharpe"] = probability >= float(
            gate["primary_anchor"]["minimum_deflated_sharpe_probability"]
        )
        passed = all(all(row.values()) for row in checks.values())
        verdict = "DISCOVERY_PASS" if passed else gate["failure_verdict"]
        expected_gate = {
            "partition": partition,
            "points": {
                point: {"checks": row, "passed": all(row.values())}
                for point, row in checks.items()
            },
            "deflated_sharpe_probability": probability,
            "deflated_sharpe_details": dsr_details,
            "passed": passed,
            "verdict": verdict,
        }
    else:
        gate = protocol.document["conditional_holdout_gate"]
        checks = {
            primary: _point_checks(
                summaries[primary], gate["primary_anchor"],
                positive_years=int(
                    gate["primary_anchor"]["minimum_positive_h00906_net_excess_calendar_years"]
                ),
                annual_floor=float(gate["primary_anchor"]["each_calendar_year_net_return_minimum"]),
            )
        }
        checks.update(
            {point: _point_checks(summaries[point], gate["neighbour_robustness"])
             for point in neighbours}
        )
        neighbour_count = sum(all(checks[point].values()) for point in neighbours)
        passed = all(checks[primary].values()) and neighbour_count >= int(
            gate["neighbour_robustness"]["minimum_passing_neighbour_count"]
        )
        verdict = gate["pass_verdict"] if passed else gate["failure_verdict"]
        expected_gate = {
            "partition": partition,
            "points": {
                point: {"checks": row, "passed": all(row.values())}
                for point, row in checks.items()
            },
            "passing_neighbour_count": neighbour_count,
            "passed": passed,
            "verdict": verdict,
        }
    if not _same(document.get("points", {}), summaries) or not _same(
        document.get("gate", {}), expected_gate
    ):
        raise R3G2Error("R3G-2 independently recomputed gate differs")
    return {"partition": partition, "passed": passed, "verdict": verdict}


def audit(
    *, release_path: Path, approval_path: Path, effect_root: Path, audit_root: Path
) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release = EffectReleaseScope.load(release_path, protocol)
    approval = EffectApproval.load(approval_path, release)
    runtime = release.verify_runtime()
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(audit_root.iterdir()):
        raise R3G2Error("R3G-2 independent audit output exists")
    report = _json(effect_root / "report.json")
    first, replay = _manifest(effect_root / "first_pass"), _manifest(effect_root / "replay")
    if (
        first != replay
        or report["first_pass"]["bundle_sha256"] != first["bundle_sha256"]
        or report["replay"]["bundle_sha256"] != replay["bundle_sha256"]
    ):
        raise R3G2Error("R3G-2 independently verified replay differs")
    discovery = _audit_partition(effect_root / "first_pass", protocol, "discovery")
    holdout_exists = (effect_root / "first_pass" / "holdout").exists()
    if discovery["passed"] is not holdout_exists:
        raise R3G2Error("R3G-2 discovery-first holdout firewall differs")
    holdout = _audit_partition(effect_root / "first_pass", protocol, "holdout") if holdout_exists else None
    verdict = discovery["verdict"] if holdout is None else holdout["verdict"]
    checks = {
        "approval_identity": report["approval_sha256"] == approval.sha256,
        "release_identity": report["release_scope_sha256"] == release.sha256,
        "attempt_count": report["strategy_effect_attempt_count"] == 3,
        "deterministic_replay": report["deterministic_replay"] is True,
        "holdout_firewall": report["holdout_outcomes_opened"] is holdout_exists,
        "terminal_verdict": report["verdict"] == verdict,
        "production_none": report["production_authorization"] == "none",
        "runtime_identity": report["runtime_identity"] == runtime,
        "effect_read_marker": _json(effect_root / "effect_read_started.json") == {
            "release_scope_sha256": release.sha256,
            "strategy_effect_attempt_count": 3,
            "discovery_first_holdout_firewall": True,
            "same_release_retry_authorized": False,
        },
    }
    if not all(checks.values()):
        raise R3G2Error(f"R3G-2 independent audit failed: {checks}")
    strategy = "HISTORICAL_GO_NOT_PRODUCTION" if verdict.startswith("GO_") else "REJECT"
    document = {
        "schema_version": "ts-v5-r3g2-effect-independent-audit-v1",
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "first_pass_bundle_sha256": first["bundle_sha256"],
        "discovery": discovery,
        "holdout": holdout,
        "checks": checks,
        "independent_audit": "PASS",
        "verdict": verdict,
        "strategy_effective": strategy,
        "production_authorization": "none",
    }
    digest, reused = write_once_json(audit_root / "audit.json", document)
    return {**document, "audit_sha256": digest, "reused": reused}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
