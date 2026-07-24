"""Synthetic-only Alpha158/LightGBM/TopK/backtest engineering smoke."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import qlib
from qlib.config import REG_CN
from qlib.contrib.data.handler import Alpha158
from qlib.contrib.evaluate import backtest_daily
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH
from qlib.workflow import R

from shaiwei.backtest.strategy import BiweeklyTopkDropoutStrategy
from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.transform.qlib_bin import QLIB_MANIFEST, qlib_tree_integrity

from tools.p2_star50_engineering.contract import GateFailure, canonical_sha256, load_protocol
from tools.p2_star50_engineering import data as data_module
from tools.p2_star50_engineering.data import _write_qlib_payload


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "synthetic_v1.json"
FORWARD_LABEL = "Ref($open,-11)/Ref($open,-1)-1"


def load_fixture() -> dict[str, Any]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    protocol = load_protocol()
    if fixture["fixture_id"] != protocol["synthetic_pipeline_contract"]["fixture_id"]:
        raise GateFailure("synthetic fixture identity differs from the frozen protocol")
    if fixture["instrument_count"] <= int(protocol["portfolio"]["topk"]):
        raise GateFailure("synthetic fixture does not provide enough instruments for TopK smoke")
    real_codes_path = PROJECT_ROOT / "data/research/star50/p2-star50-v2/daily_membership.parquet"
    real_codes = set(pd.read_parquet(real_codes_path, columns=["code"])["code"].astype(str))
    synthetic_codes = {
        f"{int(fixture['instrument_symbol_start']) + offset:06d}.SH"
        for offset in range(int(fixture["instrument_count"]))
    }
    if synthetic_codes & real_codes:
        raise GateFailure("synthetic fixture code collides with an official Star50 member")
    if fixture["benchmark_code"] in real_codes:
        raise GateFailure("synthetic benchmark code collides with an official Star50 member")
    return fixture


def _synthetic_frames(
    fixture: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    dates = pd.bdate_range(
        fixture["calendar_start"],
        periods=int(fixture["calendar_trade_days"]),
    )
    calendar = dates.strftime("%Y%m%d").tolist()
    instruments = [
        f"{int(fixture['instrument_symbol_start']) + offset:06d}.SH"
        for offset in range(int(fixture["instrument_count"]))
    ]
    time = np.arange(len(calendar), dtype=float)
    market_frames: list[pd.DataFrame] = []
    for offset, code in enumerate(instruments):
        phase = offset * 0.37
        close = (
            25.0
            + offset * 0.8
            + time * (0.012 + offset * 0.0003)
            + 0.9 * np.sin(time / 17.0 + phase)
            + 0.25 * np.cos(time / 5.0 + phase)
        )
        open_price = close * (1.0 + 0.002 * np.sin(time / 7.0 + phase))
        high = np.maximum(open_price, close) * 1.006
        low = np.minimum(open_price, close) * 0.994
        volume = 2_000_000.0 + offset * 50_000.0 + 80_000.0 * np.cos(time / 11.0 + phase)
        vwap = (open_price + close + high + low) / 4.0
        change = np.concatenate([[0.0], close[1:] / close[:-1] - 1.0])
        market_frames.append(
            pd.DataFrame(
                {
                    "ts_code": code,
                    "trade_date": calendar,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "vwap": vwap,
                    "factor": 1.0,
                    "change": change,
                    "limit_buy": False,
                    "limit_sell": False,
                }
            )
        )
    market = pd.concat(market_frames, ignore_index=True)
    benchmark_close = 1000.0 + time * 0.35 + 8.0 * np.sin(time / 21.0)
    benchmark_open = benchmark_close * (1.0 + 0.001 * np.sin(time / 9.0))
    benchmark_volume = np.full(len(calendar), 10_000_000.0)
    benchmark = pd.DataFrame(
        {
            "ts_code": fixture["benchmark_code"],
            "trade_date": calendar,
            "open": benchmark_open,
            "high": np.maximum(benchmark_open, benchmark_close) * 1.003,
            "low": np.minimum(benchmark_open, benchmark_close) * 0.997,
            "close": benchmark_close,
            "vol": benchmark_volume / 100.0,
            "amount": benchmark_close * benchmark_volume / 1000.0,
            "pct_chg": np.concatenate([[0.0], (benchmark_close[1:] / benchmark_close[:-1] - 1.0) * 100.0]),
        }
    )
    membership = pd.DataFrame(
        [{"trade_date": date, "code": code} for date in calendar for code in instruments]
    )
    return market, benchmark, membership, calendar


def _build_or_verify_provider(
    fixture: dict[str, Any],
    market: pd.DataFrame,
    benchmark: pd.DataFrame,
    membership: pd.DataFrame,
    calendar: list[str],
) -> tuple[Path, dict[str, Any]]:
    protocol = load_protocol()
    root = PROJECT_ROOT / protocol["identity"]["synthetic_root"]
    provider = root / "qlib_bin"
    identity = {
        "fixture_sha256": sha256_file(FIXTURE_PATH),
        "builder_sha256": canonical_sha256(
            {
                "synthetic": sha256_file(Path(__file__)),
                "qlib_writer": sha256_file(Path(data_module.__file__)),
            }
        ),
        "row_count": int(len(market)),
        "calendar_trade_day_count": len(calendar),
        "strategy_results_inspected": False,
        "production_authorization": "none",
    }
    identity_sha256 = canonical_sha256(identity)
    manifest_path = provider / QLIB_MANIFEST
    if provider.exists():
        if not manifest_path.is_file():
            raise GateFailure("synthetic qlib provider exists without manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("build_identity_sha256") != identity_sha256:
            raise GateFailure("synthetic qlib provider differs from the frozen fixture")
        integrity = qlib_tree_integrity(provider)
        if any(manifest.get(key) != value for key, value in integrity.items()):
            raise GateFailure("synthetic qlib provider failed integrity verification")
        return provider, {**integrity, "provider_reused": True}
    staging = provider.with_name(f".{provider.name}.building.{uuid.uuid4().hex}")
    try:
        _write_qlib_payload(
            staging,
            market,
            benchmark,
            membership,
            calendar,
            fixture["instrument_file"],
        )
        integrity = qlib_tree_integrity(staging)
        (staging / QLIB_MANIFEST).write_text(
            json.dumps(
                {
                    **identity,
                    **integrity,
                    "build_identity_sha256": identity_sha256,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        provider.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, provider)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return provider, {**integrity, "provider_reused": False}


def _date_at(calendar: list[str], position: int) -> str:
    return pd.Timestamp(calendar[position]).strftime("%Y-%m-%d")


def run_synthetic_smoke() -> dict[str, Any]:
    fixture = load_fixture()
    protocol = load_protocol()
    market, benchmark, membership, calendar = _synthetic_frames(fixture)
    provider, integrity = _build_or_verify_provider(fixture, market, benchmark, membership, calendar)
    stages = {
        "dataset": True,
        "qlib": True,
        "alpha158": False,
        "lightgbm": False,
        "topk_executor": False,
        "backtest": False,
    }
    qlib.init(provider_uri=str(provider), region=REG_CN)
    segments = {
        name: (
            _date_at(calendar, int(bounds[0])),
            _date_at(calendar, int(bounds[1])),
        )
        for name, bounds in fixture["segments"].items()
    }
    handler = Alpha158(
        instruments=fixture["instrument_file"],
        start_time=segments["train"][0],
        end_time=segments["test"][1],
        fit_start_time=segments["train"][0],
        fit_end_time=segments["train"][1],
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
    dataset = DatasetH(handler=handler, segments=segments)
    feature_rows = {
        segment: int(len(dataset.prepare(segment, col_set="feature")))
        for segment in ("train", "valid", "test")
    }
    if not all(feature_rows.values()):
        raise GateFailure("Alpha158 synthetic fixture produced an empty segment")
    stages["alpha158"] = True

    model_spec = fixture["model"]
    model = LGBModel(
        loss="mse",
        learning_rate=float(model_spec["learning_rate"]),
        num_leaves=int(model_spec["num_leaves"]),
        num_threads=1,
        seed=int(model_spec["seed"]),
        feature_fraction_seed=int(model_spec["seed"]),
        bagging_seed=int(model_spec["seed"]),
        data_random_seed=int(model_spec["seed"]),
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
        num_boost_round=int(model_spec["num_boost_round"]),
        early_stopping_rounds=int(model_spec["early_stopping_rounds"]),
    )
    # LGBModel reports validation metrics through qlib.workflow even without an
    # explicit recorder.  P2-1 forbids persisting synthetic result metrics, so
    # suppress only that logging hook while retaining the real fit operation.
    with patch.object(R, "log_metrics", return_value=None):
        model.fit(dataset, verbose_eval=False)
    predictions = model.predict(dataset, segment="test")
    if predictions.empty or predictions.isna().all():
        raise GateFailure("synthetic LightGBM smoke produced no usable predictions")
    stages["lightgbm"] = True

    strategy = BiweeklyTopkDropoutStrategy(
        signal=predictions,
        topk=int(protocol["portfolio"]["topk"]),
        n_drop=int(protocol["portfolio"]["n_drop"]),
        rebalance_days=int(protocol["portfolio"]["rebalance_trade_days"]),
        only_tradable=True,
        forbid_all_trade_at_limit=False,
    )
    stages["topk_executor"] = True
    report, positions = backtest_daily(
        start_time=segments["test"][0],
        end_time=segments["test"][1],
        strategy=strategy,
        account=100_000_000,
        benchmark="SH099999",
        exchange_kwargs={
            "deal_price": "$open",
            "limit_threshold": ("$limit_buy", "$limit_sell"),
            "open_cost": float(protocol["execution"]["open_cost"]),
            "close_cost": float(protocol["execution"]["close_cost"]),
            "min_cost": float(protocol["execution"]["minimum_cost_rmb"]),
        },
    )
    if report.empty or not positions:
        raise GateFailure("synthetic TopK backtest smoke produced no executor observations")
    position_values = positions.values() if hasattr(positions, "values") else positions
    non_cash_position_observations = sum(
        bool(position.get_stock_list()) for position in position_values if hasattr(position, "get_stock_list")
    )
    if non_cash_position_observations == 0:
        raise GateFailure("synthetic TopK executor never formed a non-cash position")
    stages["backtest"] = True
    del predictions, report, positions, model, dataset, handler, strategy

    required_stages = list(protocol["synthetic_pipeline_contract"]["required_stages"])
    if set(stages) != set(required_stages) or not all(stages.values()):
        raise GateFailure("synthetic pipeline did not complete every frozen stage")
    smoke = {
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": sha256_file(FIXTURE_PATH),
        "stage_status": stages,
        "row_counts": {
            "calendar_trade_days": len(calendar),
            "synthetic_instruments": int(fixture["instrument_count"]),
            "synthetic_market_rows": int(len(market)),
            "alpha158_train_rows": feature_rows["train"],
            "alpha158_valid_rows": feature_rows["valid"],
            "alpha158_test_rows": feature_rows["test"],
            "synthetic_prediction_rows_ephemeral": int(feature_rows["test"]),
            "synthetic_backtest_trade_days_ephemeral": int(
                fixture["segments"]["test"][1] - fixture["segments"]["test"][0] + 1
            ),
            "synthetic_non_cash_position_observations_ephemeral": int(non_cash_position_observations),
        },
        "artifact_sha256": {
            "synthetic_qlib_tree": integrity["artifact_sha256"],
        },
        "pipeline_fixture_pass": True,
    }
    allowed = set(protocol["synthetic_pipeline_contract"]["allowed_report_fields"])
    if set(smoke) != allowed:
        raise GateFailure("synthetic smoke report fields exceed the frozen allowlist")
    output = PROJECT_ROOT / protocol["identity"]["synthetic_root"] / "smoke_report.json"
    rendered = json.dumps(smoke, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise GateFailure("synthetic smoke report is not idempotent")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return smoke
