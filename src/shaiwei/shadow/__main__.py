"""Train the current Alpha158 baseline and emit one immutable shadow signal."""

import argparse
import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from dateutil.relativedelta import relativedelta
from qlib.contrib.data.handler import Alpha158
from qlib.data import D
from qlib.data.dataset import DatasetH
from qlib.workflow import R

from shaiwei.backtest.baseline import FORWARD_LABEL, _model
from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import append_experiment, ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.shadow.manifest import write_signal_manifest


def _matching_sentinel_report(data_hash: str, code_hash: str) -> dict[str, object]:
    report_dir = PROJECT_ROOT / "logs" / "sentinels"
    for path in sorted(report_dir.glob("*.json"), reverse=True):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("data_snapshot_sha256") == data_hash and report.get("code_snapshot_sha256") == code_hash:
            return report
    raise RuntimeError("no sentinel report matches the current data and code snapshots")


def _scores_for_date(signal_date: date) -> tuple[pd.DataFrame, dict[str, str]]:
    settings = load()
    train_start = signal_date - relativedelta(years=3)
    valid_start = signal_date - relativedelta(months=settings.baseline.validation_months)
    train_end = valid_start - timedelta(days=1)
    segments = {
        "train": (train_start.isoformat(), train_end.isoformat()),
        "valid": (valid_start.isoformat(), signal_date.isoformat()),
        "test": (signal_date.isoformat(), signal_date.isoformat()),
    }
    handler = Alpha158(
        instruments=settings.baseline.instrument,
        start_time=train_start.isoformat(),
        end_time=signal_date.isoformat(),
        fit_start_time=segments["train"][0],
        fit_end_time=segments["train"][1],
        infer_processors=[
            {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
        ],
        learn_processors=[{"class": "DropnaLabel"}, {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}}],
        label=([FORWARD_LABEL], ["LABEL0"]),
    )
    dataset = DatasetH(handler=handler, segments=segments)
    model = _model(settings)
    with R.start(experiment_name="stage0_shadow_alpha158"):
        model.fit(dataset, verbose_eval=50)
        predictions = model.predict(dataset, segment="test")
    scores = predictions.rename("score").reset_index()
    if "instrument" not in scores.columns:
        raise RuntimeError(f"qlib predictions missing instrument index: {scores.columns.tolist()}")
    return scores.loc[:, ["instrument", "score"]], {key: f"{value[0]}~{value[1]}" for key, value in segments.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成阶段 0 影子执行信号 manifest")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    settings = load()
    initialize_qlib(settings)
    calendar = D.calendar(start_time=settings.backtest.start, end_time=args.as_of, freq="day")
    if not len(calendar):
        raise SystemExit(f"no qlib trading day on or before {args.as_of}")
    signal_date = pd.Timestamp(calendar[-1]).date()
    data_hash = ingest_snapshot_sha256()
    code_hash = code_snapshot_sha256()
    sentinel_report = _matching_sentinel_report(data_hash, code_hash)
    generated_at = datetime.now(timezone.utc)
    scores, segments = _scores_for_date(signal_date)
    path, signal_hash = write_signal_manifest(
        scores,
        signal_date=signal_date,
        topk=settings.backtest.topk,
        sentinel_results=sentinel_report["results"],
        data_complete_at=datetime.fromisoformat(str(sentinel_report["generated_at"])),
        generated_at=generated_at,
        data_snapshot_sha256=data_hash,
        code_commit=git_head(),
        code_snapshot_sha256=code_hash,
        output_dir=PROJECT_ROOT / "signals",
        environment=settings.runtime.environment,
    )
    append_experiment(
        candidate_source="Alpha158-shadow",
        model_or_engine="LightGBM",
        engine_version="4.6.0",
        seed=settings.baseline.seed,
        prompt_hash="",
        code_sha256=code_hash,
        data_snapshot_sha256=data_hash,
        feature_or_formula=f"Alpha158; label={FORWARD_LABEL}",
        params_json={"segments": segments, "topk": settings.backtest.topk},
        train_period=segments["train"],
        valid_period=f"{segments['valid']}; signal={signal_date}",
        result_json={"signal_sha256": signal_hash, "manifest_path": str(path), "score_rows": len(scores)},
        admitted=False,
        reject_reason="stage0 shadow signal; not a factor-admission experiment",
    )
    print(json.dumps({"signal_date": str(signal_date), "signal_sha256": signal_hash, "manifest_path": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
