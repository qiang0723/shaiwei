"""g1-v2 开发集检查（`g1-positive-control-v2` §5，用户裁决 D4）。

在 v1 正式执行落盘的面板上计算 g1-v2 新统计量，**只报告分布**：不判定、不调阈值、不改选项或构造、不写任何账本。
v1 面板按 g1-v1 中性化构建（标签非空支撑），结果只检查可计算性与量级，不是 g1-v2 的标定。
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.research.factor_portfolio import augment_signal, daily_rank_ic
from shaiwei.research.g1 import G1Error, deflated_sharpe_probability, newey_west_mean_t, periodic_sharpe
from shaiwei.research.g1_calibration.protocol import CONFIG_PATH_V2, ProtocolIdentity, load_protocol
from shaiwei.research.g1_pipeline import BaselineWindow
from shaiwei.research.g1_v2 import load_spec, paired_differences

SCOPE_NOTE = "development set only: distributions of g1-v2 statistics on v1 panels (v1 neutralization); no decision, threshold or option is derived"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _dated(series: pd.Series) -> dict[str, float]:
    return {pd.Timestamp(day).date().isoformat(): float(value) for day, value in series.items()}


def _spread(values: list[float]) -> dict[str, float] | None:
    clean = [value for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return None
    return {"min": min(clean), "median": statistics.median(clean), "max": max(clean), "n": len(clean)}


def devset(settings: Settings, protocol: ProtocolIdentity, *, baselines: list[BaselineWindow], v1_reports_dir: Path) -> dict[str, object]:
    spec = load_spec(settings, PROJECT_ROOT / protocol.config.judge.spec_config).spec  # type: ignore[union-attr]
    threshold = spec.thresholds
    summary = json.loads((v1_reports_dir / "summary.json").read_text(encoding="utf-8"))
    baseline_ic = _dated(pd.concat([window.daily_ic for window in baselines]).sort_index())
    baseline_excess = pd.concat([window.backtest.daily_excess for window in baselines]).sort_index()
    units: list[dict[str, object]] = []
    increments_by_cell: dict[str, list[tuple[int, list[float]]]] = defaultdict(list)
    for unit in summary["units"]:
        if unit["status"] != "JUDGED":
            continue
        report = json.loads(_path(unit["report_path"]).read_text(encoding="utf-8"))
        evidence = json.loads(_path(report["bindings"]["evidence_path"]).read_text(encoding="utf-8"))
        tests = json.loads(_path(evidence["integrity"]["test_report_path"]).read_text(encoding="utf-8"))
        panel = pd.read_parquet(_path(tests["factor_panel_path"]))
        factor = panel.set_index(["datetime", "instrument"])["factor"].sort_index()
        oriented = (1.0 if evidence["rank_ic"]["in_sample"] > 0 else -1.0) * factor
        parts = []
        for window in baselines:
            score = oriented if unit["route"] == "R2" else augment_signal(window.predictions, oriented, factor_weight=threshold.factor_blend_weight)
            parts.append(daily_rank_ic(score, window.labels))
        increments = paired_differences(_dated(pd.concat(parts).sort_index()), baseline_ic)
        candidate_excess = evidence["portfolio"]["daily_net_excess_returns"]
        entry: dict[str, object] = {key: unit[key] for key in ("route", "strength", "seed", "cell_family", "experiment_id")}
        try:
            entry["increment_t"] = newey_west_mean_t(increments, lags=threshold.hac_lags, minimum=threshold.min_observations)
            entry["increment_ir"] = periodic_sharpe(increments, minimum=threshold.min_observations)
        except G1Error as error:
            entry["increment_error"] = type(error).__name__
        if len(candidate_excess) == len(baseline_excess):  # v1 证据未存日期：只在长度一致时按日期顺序配对
            excess = [float(c) - float(b) for c, b in zip(candidate_excess, baseline_excess, strict=True)]
            entry["excess_t"] = newey_west_mean_t(excess, lags=threshold.hac_lags, minimum=threshold.min_observations)
        else:
            entry["excess_alignment"] = f"candidate {len(candidate_excess)} vs baseline {len(baseline_excess)} days"
        entry["observations"] = len(increments)
        units.append(entry)
        increments_by_cell[str(unit["cell_family"])].append((len(units) - 1, increments))
    for cell, members in increments_by_cell.items():
        irs = tuple(float(units[i]["increment_ir"]) for i, _ in members if "increment_ir" in units[i])
        for index, increments in members:
            if "increment_ir" in units[index] and len(irs) >= threshold.min_valid_trial_increment_irs:
                units[index]["increment_dsr_cell"], _ = deflated_sharpe_probability(
                    increments, trial_sharpes=irs, trial_count=len(members), minimum=threshold.min_observations
                )
    cells = {
        cell: {metric: _spread([float(units[i][metric]) for i, _ in members if metric in units[i]])
               for metric in ("increment_t", "increment_ir", "excess_t", "increment_dsr_cell")}
        for cell, members in sorted(increments_by_cell.items())
    }
    return {
        "schema_version": 1, "protocol_id": protocol.config.protocol_id, "scope": SCOPE_NOTE,
        "source_execution": summary["execution_id"], "spec_sha256": protocol.config.judge.spec_config_sha256,  # type: ignore[union-attr]
        "units": units, "cells": cells,
    }


def main(argv: list[str] | None = None) -> int:
    from shaiwei.research.g1_pipeline import build_baseline_windows, load_research_data

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=CONFIG_PATH_V2)
    args = parser.parse_args(argv)
    settings = load()
    protocol = load_protocol(settings, args.protocol)
    if protocol.version != "v2":
        raise SystemExit("the development set belongs to g1-positive-control-v2")
    allowed = (PROJECT_ROOT / protocol.config.isolation.reports_dir / "dev-set").resolve()
    if not args.output.resolve().is_relative_to(allowed) or args.output.exists():
        raise SystemExit(f"dev-set output must be a new file under {allowed}")
    source = protocol.config.development_set.source_execution  # type: ignore[union-attr]
    research = load_research_data(settings)
    baselines = build_baseline_windows(settings, research.labels)
    report = devset(settings, protocol, baselines=baselines, v1_reports_dir=PROJECT_ROOT / "logs" / "g1-calibration" / source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"units": len(report["units"]), "cells": len(report["cells"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
