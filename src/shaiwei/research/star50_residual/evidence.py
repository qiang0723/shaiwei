"""Deterministic M4-0 evidence assembly and immutable artifact writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import uuid

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual.compute import CANDIDATES, ResidualInputs
from shaiwei.research.star50_residual.contract import (
    ResidualGateError,
    ResidualExecutionRelease,
    ResidualProtocol,
    canonical_sha256,
    sha256_file,
)


def code_bundle_sha256(*, project_root: Path = PROJECT_ROOT) -> str:
    root = project_root / "src/shaiwei/research/star50_residual"
    names = ("contract.py", "compute.py", "evidence.py", "run.py", "audit.py")
    return canonical_sha256({name: sha256_file(root / name) for name in names})


def _write_immutable_parquet(frame: pd.DataFrame, path: Path) -> tuple[str, bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(staging, index=False, compression="zstd")
    digest = sha256_file(staging)
    if path.exists():
        if sha256_file(path) != digest:
            staging.unlink()
            raise ResidualGateError("M4-0 immutable feature artifact differs")
        staging.unlink()
        return digest, True
    os.replace(staging, path)
    return digest, False


def _write_immutable_json(document: dict[str, Any], path: Path) -> tuple[str, bool]:
    rendered = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise ResidualGateError("M4-0 immutable quality report differs")
        return sha256_file(path), True
    path.write_text(rendered, encoding="utf-8")
    return sha256_file(path), False


def build_quality_report(
    protocol: ResidualProtocol,
    release: ResidualExecutionRelease,
    inputs: ResidualInputs,
    features: pd.DataFrame,
    denominator: pd.DataFrame,
    *,
    project_root: Path = PROJECT_ROOT,
) -> tuple[dict[str, Any], Path]:
    gate = protocol.document["data_gate"]
    identity = protocol.document["identity"]
    feature_path = project_root / identity["feature_artifact"]

    duplicate_keys = int(features.duplicated(["trade_date", "ts_code"], keep=False).sum())
    numeric_columns = [*CANDIDATES, "alpha", "beta", "residual_std"]
    numeric = features[numeric_columns].to_numpy(dtype=float) if len(features) else np.empty((0, 6))
    nonfinite = int((~np.isfinite(numeric)).sum())
    bse_rows = int(features["ts_code"].astype(str).str.endswith(".BJ", na=False).sum())
    denominator_count = int(len(denominator))
    coverage = {
        candidate: (float(features[candidate].notna().sum() / denominator_count) if denominator_count else 0.0)
        for candidate in CANDIDATES
    }
    signal_dates = sorted(inputs.members["trade_date"].astype(str).unique())
    daily_minimum = {
        candidate: int(
            features.groupby("trade_date")[candidate].count().reindex(signal_dates, fill_value=0).min()
        )
        for candidate in CANDIDATES
    }
    checks = {
        "candidate_count_exact": len(CANDIDATES) == int(gate["candidate_count_exact"]),
        "candidate_coverage_pass": all(
            value >= float(gate["candidate_coverage_minimum_each"]) for value in coverage.values()
        ),
        "minimum_daily_finite_pass": all(
            value >= int(gate["minimum_finite_candidates_per_signal_day_each"])
            for value in daily_minimum.values()
        ),
        "duplicate_feature_key_pass": duplicate_keys
        <= int(gate["duplicate_feature_key_count_maximum"]),
        "nonfinite_persisted_value_pass": nonfinite
        <= int(gate["nonfinite_persisted_values_maximum"]),
        "bse_pass": bse_rows <= int(gate["bse_row_count_maximum"]),
    }
    verdict = gate["verdict_on_pass"] if all(checks.values()) else gate["verdict_on_failure"]
    feature_sha256, feature_reused = _write_immutable_parquet(features, feature_path)
    report = {
        "schema_version": "m4-star50-residual-quality-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "execution_release_sha256": release.sha256,
        "implementation_git_head": release.document["implementation_git_head"],
        "code_bundle_sha256": code_bundle_sha256(project_root=project_root),
        "upstream_evidence": protocol.verify_upstream(project_root=project_root),
        "input": {
            "member_day_count": int(len(inputs.members)),
            "signal_trade_day_count": int(inputs.members["trade_date"].nunique()),
            "market_input_row_count": int(len(inputs.market)),
            "benchmark_input_row_count": int(len(inputs.benchmark)),
            "maximum_input_date": max(
                str(inputs.members["trade_date"].max()),
                str(inputs.market["trade_date"].max()),
                str(inputs.benchmark["trade_date"].max()),
            ),
            "coverage_denominator_count": denominator_count,
        },
        "feature_gate": {
            "candidate_ids": list(CANDIDATES),
            "feature_row_count": int(len(features)),
            "candidate_coverage": coverage,
            "minimum_daily_finite_count": daily_minimum,
            "duplicate_feature_key_count": duplicate_keys,
            "nonfinite_persisted_value_count": nonfinite,
            "bse_row_count": bse_rows,
            "checks": checks,
        },
        "artifact": {
            "path": identity["feature_artifact"],
            "row_count": int(len(features)),
            "sha256": feature_sha256,
        },
        "factor_effect_or_rank_ic_computed": False,
        "label_read": False,
        "sealed_validation_read": False,
        "provider_calls": 0,
        "api_key_read": False,
        "model_backtest_portfolio_signal_run": False,
        "strategy_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report_path = project_root / identity["quality_report"]
    report_sha256, report_reused = _write_immutable_json(report, report_path)
    return {
        **report,
        "quality_report_sha256": report_sha256,
        "artifact_reused": feature_reused,
        "quality_report_reused": report_reused,
    }, report_path
