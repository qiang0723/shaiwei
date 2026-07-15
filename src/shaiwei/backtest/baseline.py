"""Alpha158 + LightGBM 六滚动窗基线与 G0 成本情景证据。"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
import qlib
from dateutil.relativedelta import relativedelta
from qlib.config import REG_CN
from qlib.contrib.data.handler import Alpha158
from qlib.contrib.evaluate import backtest_daily
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH
from qlib.workflow import R

from shaiwei.backtest.strategy import BiweeklyTopkDropoutStrategy
from shaiwei.config import PROJECT_ROOT, EvaluationWindow, Settings, load
from shaiwei.ledger import append_experiment, ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256

FORWARD_LABEL = "Ref($open, -11) / Ref($open, -1) - 1"


@dataclass(frozen=True)
class WindowSegments:
    train: tuple[str, str]
    valid: tuple[str, str]
    test: tuple[str, str]


def window_segments(window: EvaluationWindow, validation_months: int) -> WindowSegments:
    valid_start = window.train_end - relativedelta(months=validation_months) + timedelta(days=1)
    train_end = valid_start - timedelta(days=1)
    if train_end < window.train_start:
        raise ValueError(f"validation split consumes training window: {window.name}")
    return WindowSegments(
        train=(window.train_start.isoformat(), train_end.isoformat()),
        valid=(valid_start.isoformat(), window.train_end.isoformat()),
        test=(window.test_start.isoformat(), window.test_end.isoformat()),
    )


def cost_scenario_metrics(report: pd.DataFrame, multipliers: list[float]) -> dict[str, dict[str, float]]:
    required = {"return", "bench", "cost"}
    if missing := required - set(report.columns):
        raise ValueError(f"qlib report missing fields: {sorted(missing)}")
    metrics = {}
    for multiplier in multipliers:
        strategy_daily = report["return"].fillna(0.0) - multiplier * report["cost"].fillna(0.0)
        benchmark_daily = report["bench"].fillna(0.0)
        strategy_nav = float((1.0 + strategy_daily).prod())
        benchmark_nav = float((1.0 + benchmark_daily).prod())
        excess = strategy_nav / benchmark_nav - 1.0
        metrics[f"{multiplier:g}"] = {
            "strategy_return": strategy_nav - 1.0,
            "benchmark_return": benchmark_nav - 1.0,
            "cumulative_excess": excess,
            "reported_cost_sum": float((multiplier * report["cost"].fillna(0.0)).sum()),
        }
    return metrics


def g0_backtest_summary(window_results: list[dict], baseline_multiplier: float = 1.0) -> dict[str, object]:
    baseline_key = f"{baseline_multiplier:g}"
    positive = sum(result["cost_scenarios"][baseline_key]["cumulative_excess"] > 0 for result in window_results)
    combined = {}
    if window_results:
        scenario_keys = window_results[0]["cost_scenarios"]
        for key in scenario_keys:
            combined[key] = float(
                pd.Series(
                    [1.0 + result["cost_scenarios"][key]["cumulative_excess"] for result in window_results]
                ).prod()
                - 1.0
            )
    return {
        "window_count": len(window_results),
        "positive_excess_windows": positive,
        "combined_cumulative_excess": combined,
        "window_condition_pass": len(window_results) == 6 and positive >= 4,
        "cost_1_5_condition_pass": combined.get("1.5", float("-inf")) >= 0,
    }


def _model(settings: Settings) -> LGBModel:
    baseline = settings.baseline
    return LGBModel(
        loss="mse",
        learning_rate=baseline.learning_rate,
        num_leaves=baseline.num_leaves,
        max_depth=baseline.max_depth,
        colsample_bytree=baseline.colsample_bytree,
        subsample=baseline.subsample,
        reg_alpha=baseline.reg_alpha,
        reg_lambda=baseline.reg_lambda,
        num_threads=settings.compute.joblib_max_procs,
        seed=baseline.seed,
        feature_fraction_seed=baseline.seed,
        bagging_seed=baseline.seed,
        data_random_seed=baseline.seed,
        deterministic=True,
        force_col_wise=True,
        num_boost_round=baseline.num_boost_round,
        early_stopping_rounds=baseline.early_stopping_rounds,
    )


def run_window(settings: Settings, window: EvaluationWindow) -> dict[str, object]:
    segments = window_segments(window, settings.baseline.validation_months)
    handler = Alpha158(
        instruments=settings.baseline.instrument,
        start_time=window.train_start.isoformat(),
        end_time=window.test_end.isoformat(),
        fit_start_time=segments.train[0],
        fit_end_time=segments.train[1],
        infer_processors=[
            {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
        ],
        learn_processors=[
            {"class": "DropnaLabel"},
            {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}},
        ],
        label=([FORWARD_LABEL], ["LABEL0"]),
    )
    dataset = DatasetH(handler=handler, segments=asdict(segments))
    model = _model(settings)
    with R.start(experiment_name="stage0_alpha158_lightgbm"):
        model.fit(dataset, verbose_eval=50)
        predictions = model.predict(dataset, segment="test")
    strategy = BiweeklyTopkDropoutStrategy(
        signal=predictions,
        topk=settings.backtest.topk,
        n_drop=settings.backtest.n_drop,
        rebalance_days=settings.backtest.rebalance_days,
        only_tradable=True,
        forbid_all_trade_at_limit=False,
    )
    report, _ = backtest_daily(
        start_time=window.test_start.isoformat(),
        end_time=window.test_end.isoformat(),
        strategy=strategy,
        account=settings.baseline.account,
        benchmark=settings.backtest.benchmark,
        exchange_kwargs={
            "deal_price": settings.backtest.deal_price,
            "limit_threshold": ("$limit_buy", "$limit_sell"),
            "open_cost": settings.backtest.open_cost,
            "close_cost": settings.backtest.close_cost,
            "min_cost": settings.backtest.min_cost,
        },
    )
    return {
        "window": window.name,
        "segments": asdict(segments),
        "prediction_rows": len(predictions),
        "cost_scenarios": cost_scenario_metrics(report, settings.backtest.cost_scenarios),
    }


def _record_window(settings: Settings, window: EvaluationWindow, result: dict, *, error: str = "") -> None:
    segments = window_segments(window, settings.baseline.validation_months)
    append_experiment(
        candidate_source="Alpha158",
        model_or_engine="LightGBM",
        engine_version="4.6.0",
        seed=settings.baseline.seed,
        prompt_hash="",
        code_sha256=code_snapshot_sha256(),
        data_snapshot_sha256=ingest_snapshot_sha256(),
        feature_or_formula=f"Alpha158; label={FORWARD_LABEL}",
        params_json={
            "window": window.name,
            "topk": settings.backtest.topk,
            "n_drop": settings.backtest.n_drop,
            "rebalance_days": settings.backtest.rebalance_days,
            "cost_scenarios": settings.backtest.cost_scenarios,
            "baseline": settings.baseline.model_dump(mode="json"),
        },
        train_period=f"{segments.train[0]}~{segments.train[1]}",
        valid_period=f"{segments.valid[0]}~{segments.valid[1]}; test={segments.test[0]}~{segments.test[1]}",
        result_json=result,
        admitted=False,
        reject_reason=error or "stage0 baseline evidence; not a factor-admission experiment",
    )


def main() -> int:
    settings = load()
    qlib.init(provider_uri=str(settings.runtime.data_root / "qlib_bin"), region=REG_CN)
    results = []
    for window in settings.evaluation.g0_windows:
        try:
            result = run_window(settings, window)
        except Exception as error:
            _record_window(settings, window, {"status": "failed"}, error=f"{type(error).__name__}: {error}")
            raise
        _record_window(settings, window, result)
        results.append(result)
    summary = g0_backtest_summary(results)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "data_snapshot_sha256": ingest_snapshot_sha256(),
        "forward_label": FORWARD_LABEL,
        "windows": results,
        "g0_backtest": summary,
    }
    output_dir = PROJECT_ROOT / "logs" / "backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"stage0_baseline_{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**payload, "report_path": str(output)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
