"""计时试跑与上下文载入（协议 §10 第 3 步）：只用协议外种子，不写任何账本、不判定、不输出指标值。"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from typing import Callable, TypeVar
from pathlib import Path

from shaiwei.config import Settings, load
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_calibration.evidence import build_increment_series, build_portfolio_evidence
from shaiwei.research.g1_calibration.protocol import CONFIG_PATH, ProtocolIdentity, load_protocol
from shaiwei.research.g1_calibration.signals import RunContext, Unit, build_signal, plan_cells

T = TypeVar("T")


def build_r5_stock_data(settings: Settings) -> object:
    import torch
    from alphagen_qlib.stock_data import StockData

    from shaiwei.benchmark.alphagen_cpu import stock_data_effective_start

    start = min(settings.g1_admission.discovery_start, *(p.start for p in settings.evaluation.stress_periods))
    end = max(*(w.test_end for w in settings.evaluation.g0_windows), *(p.end for p in settings.evaluation.stress_periods))
    effective_start = stock_data_effective_start(start, controls.R5_BACKTRACK_DAYS)
    return StockData(
        settings.baseline.instrument, effective_start.isoformat(), end.isoformat(),
        max_backtrack_days=controls.R5_BACKTRACK_DAYS, max_future_days=settings.backtest.rebalance_days + 1,
        device=torch.device("cpu"),
    )


def _timed(timings: dict[str, float], stage: str, build: Callable[[], T]) -> T:
    """逐阶段即时打印耗时（只含阶段名与秒数）：中途失败也不丢已测得的时间。"""
    started = time.monotonic()
    value = build()
    timings[stage] = round(time.monotonic() - started, 3)
    print(json.dumps({"stage": stage, "seconds": timings[stage]}), flush=True)
    return value


def load_context(settings: Settings, protocol: ProtocolIdentity, timings: dict[str, float]) -> RunContext:
    from shaiwei.ledger import ingest_snapshot_sha256
    from shaiwei.provenance import code_snapshot_sha256
    from shaiwei.research.g1_pipeline import build_baseline_windows, load_research_data

    controls.verify_route_expressions(protocol.config)
    research = _timed(timings, "load_research_data", lambda: load_research_data(settings))
    r5 = _timed(timings, "build_r5_stock_data", lambda: build_r5_stock_data(settings))
    baselines = _timed(timings, "build_baseline_windows", lambda: build_baseline_windows(settings, research.labels))
    return RunContext(settings, protocol, research, r5, baselines, code_snapshot_sha256(), ingest_snapshot_sha256())


PILOT_UNITS = (Unit("R1", 0.04, 0), Unit("N1", None, 0))  # 协议外种子：试跑不预览任何正式评估


def pilot_units(protocol: ProtocolIdentity) -> tuple[Unit, ...]:
    return (*PILOT_UNITS, Unit("N3", None, 0)) if "N3" in protocol.config.routes else PILOT_UNITS


def pilot(ctx: RunContext, timings: dict[str, float]) -> dict[str, object]:
    """只计时：构造信号与组合证据后即丢弃，不落盘证据、不记账、不判定、不输出任何指标值。"""
    per_unit = {}
    units = pilot_units(ctx.protocol)
    for unit in units:
        started = time.monotonic()
        signal = build_signal(ctx, unit)
        built = time.monotonic()
        if unit.route == "N3":  # 增量对照只算两条 RankIC 序列，不回测
            build_increment_series(ctx.settings, factor=signal.residual, baselines=ctx.baselines)
        else:
            build_portfolio_evidence(
                ctx.settings, factor=signal.residual, factor_daily_ic=signal.daily_ic, labels=ctx.research.labels,
                baselines=ctx.baselines, mode="blend", backtest=ctx.backtest,
            )
        per_unit[unit.route] = {"signal_seconds": round(built - started, 3), "evidence_seconds": round(time.monotonic() - built, 3)}
        print(json.dumps({"stage": f"pilot_unit_{unit.route}", **per_unit[unit.route]}), flush=True)
        ctx.cache.clear()
    fixed = sum(timings.values())
    evidence = max(item["evidence_seconds"] for key, item in per_unit.items() if key != "N3")
    n3_seconds = sum(per_unit["N3"].values()) if "N3" in per_unit else 0.0
    projections = {}
    for noise in (30, 20, 10):
        cells = plan_cells(ctx.protocol, noise)
        evaluations = sum(len(cell) for cell in cells)
        n3_count = sum(len(cell) for cell in cells if cell[0].route == "N3")
        r1_signals = len(cells[0]) * len(ctx.protocol.config.calibration.target_mean_rank_ic)
        seconds = (
            fixed + (evaluations - n3_count) * evidence + r1_signals * per_unit["R1"]["signal_seconds"]
            + 2 * noise * per_unit["N1"]["signal_seconds"] + n3_count * n3_seconds
        )
        projections[str(noise)] = {"evaluations": evaluations, "projected_hours": round(seconds / 3600, 2)}
    return {
        "schema_version": 1, "protocol_id": ctx.protocol.config.protocol_id, "pilot_units": [asdict(unit) for unit in units],
        "fixed_seconds": timings, "per_unit_seconds": per_unit, "projections": projections,
        "budget_max_hours": ctx.protocol.config.budget.max_hours, "result_blind": "no metric, gate or IC value is recorded",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", required=True, help="计时试跑；正式执行另由 release scope 授权")
    parser.add_argument("--output", type=Path, required=True, help="试跑耗时报告路径（须在标定数据目录下）")
    parser.add_argument("--protocol", type=Path, default=CONFIG_PATH, help="冻结的正控协议配置（默认 v1）")
    args = parser.parse_args(argv)
    settings = load()
    protocol = load_protocol(settings, args.protocol)
    expected_root = (settings.runtime.data_root / "research" / protocol.config.family).resolve()
    if not args.output.resolve().is_relative_to(expected_root) or args.output.exists():
        raise SystemExit(f"pilot output must be a new file under {expected_root}")
    timings: dict[str, float] = {}
    report = pilot(load_context(settings, protocol, timings), timings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["projections"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

