"""Immutable M4-1 artifacts, deterministic hashes, and append-only ledgers."""

from __future__ import annotations

import csv
import fcntl
import json
import os
from pathlib import Path
from typing import Any
import uuid

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual_effect.contract import (
    ResidualEffectError,
    canonical_sha256,
    sha256_file,
)


CODE_BUNDLE_PATHS = (
    "src/shaiwei/research/star50_residual_effect/contract.py",
    "src/shaiwei/research/star50_residual_effect/data.py",
    "src/shaiwei/research/star50_residual_effect/metrics.py",
    "src/shaiwei/research/star50_residual_effect/judge.py",
    "src/shaiwei/research/star50_residual_effect/evidence.py",
    "src/shaiwei/research/star50_residual_effect/run.py",
    "src/shaiwei/research/star50_residual_effect/audit.py",
    "src/shaiwei/research/star50_residual/compute.py",
    "src/shaiwei/research/g1.py",
    "src/shaiwei/research/g1_pipeline.py",
    "src/shaiwei/research/factor_portfolio.py",
    "tools/p2_star50_effect/metrics.py",
    "tools/p2_star50_effect_correction/executor.py",
)


def code_bundle_sha256(*, project_root: Path = PROJECT_ROOT) -> str:
    return canonical_sha256(
        {path: sha256_file(project_root / path) for path in CODE_BUNDLE_PATHS}
    )


def frame_hash(frame: pd.DataFrame, sort_columns: list[str]) -> str:
    ordered = frame.sort_values(sort_columns).reset_index(drop=True) if len(frame) else frame.copy()
    records: list[dict[str, Any]] = []
    for row in ordered.to_dict("records"):
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (float, np.floating)):
                normalized[key] = None if pd.isna(value) else float(value).hex()
            elif isinstance(value, (int, np.integer)):
                normalized[key] = int(value)
            elif pd.isna(value):
                normalized[key] = None
            else:
                normalized[key] = str(value)
        records.append(normalized)
    return canonical_sha256(records)


def write_parquet(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    digest = sha256_file(temporary)
    if path.exists():
        if sha256_file(path) != digest:
            temporary.unlink(missing_ok=True)
            raise ResidualEffectError(f"M4-1 immutable parquet differs: {path.name}")
        temporary.unlink(missing_ok=True)
        reused = True
    else:
        os.replace(temporary, path)
        reused = False
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": digest,
        "rows": int(len(frame)),
        "reused": reused,
    }


def write_json(document: dict[str, Any], path: Path) -> tuple[str, bool]:
    rendered = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise ResidualEffectError(f"M4-1 immutable JSON differs: {path.name}")
        return sha256_file(path), True
    path.write_text(rendered, encoding="utf-8")
    return sha256_file(path), False


def save_pass(
    pass_root: Path,
    *,
    features: pd.DataFrame,
    core: pd.DataFrame,
    incremental: pd.DataFrame,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    artifacts = {
        "extended_features": write_parquet(features, pass_root / "extended_features.parquet"),
        "core_residuals": write_parquet(core, pass_root / "core_residuals.parquet"),
        "incremental_residuals": write_parquet(
            incremental, pass_root / "incremental_residuals.parquet"
        ),
    }
    returns = (
        pd.concat([row["return_rows"] for row in results], ignore_index=True)
        if results
        else pd.DataFrame(
            columns=[
                "candidate",
                "window",
                "scenario",
                "trade_date",
                "daily_net_return",
                "benchmark_return",
                "nav_open",
                "nav",
                "cash",
            ]
        )
    )
    ic_rows = (
        pd.concat([row["ic_rows"] for row in results], ignore_index=True)
        if results
        else pd.DataFrame(
            columns=["candidate", "window", "series_type", "trade_date", "rank_ic"]
        )
    )
    artifacts["daily_executions"] = write_parquet(
        returns, pass_root / "daily_executions.parquet"
    )
    artifacts["daily_rank_ic"] = write_parquet(ic_rows, pass_root / "daily_rank_ic.parquet")
    canonical = {
        "extended_features": frame_hash(features, ["trade_date", "ts_code"]),
        "core_residuals": frame_hash(core, ["trade_date", "ts_code"]),
        "incremental_residuals": frame_hash(incremental, ["trade_date", "ts_code"]),
        "daily_executions": frame_hash(
            returns, ["candidate", "window", "scenario", "trade_date"]
        ),
        "daily_rank_ic": frame_hash(
            ic_rows, ["candidate", "window", "series_type", "trade_date"]
        ),
    }
    physical = {name: value["sha256"] for name, value in artifacts.items()}
    return {"artifacts": artifacts, "canonical": canonical, "physical": physical}


RUN_FIELDS = (
    "run_id",
    "protocol_sha256",
    "execution_release_sha256",
    "implementation_git_head",
    "code_bundle_sha256",
    "input_snapshot_sha256",
    "run_started_at",
    "run_finished_at",
    "direction_pass_count",
    "adapted_gate_pass_count",
    "formal_g1_v1_status",
    "determinism_pass",
    "verdict",
    "strategy_effective",
    "production_authorization",
    "effect_report_sha256",
)

DECISION_FIELDS = (
    "decision_id",
    "run_id",
    "candidate",
    "direction_pass",
    "oos_effect_read",
    "adapted_gate_decision",
    "failed_gates",
    "formal_g1_v1_status",
    "production_authorization",
    "effect_report_sha256",
)


def append_once(path: Path, fields: tuple[str, ...], row: dict[str, Any], identity: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(f"{path.suffix}.lock")
    with lock.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        existing: list[dict[str, str]] = []
        has_header = path.exists() and path.stat().st_size > 0
        if path.exists():
            with path.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                if tuple(reader.fieldnames or ()) != fields:
                    raise ResidualEffectError(f"M4-1 ledger schema differs: {path.name}")
                existing = list(reader)
        normalized = {field: str(row.get(field, "")) for field in fields}
        matches = [item for item in existing if item[fields[0]] == identity]
        if matches:
            if len(matches) != 1 or matches[0] != normalized:
                raise ResidualEffectError(f"M4-1 ledger identity conflict: {identity}")
            return True
        with path.open("a", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            if not has_header:
                writer.writeheader()
            writer.writerow(normalized)
            target.flush()
            os.fsync(target.fileno())
        return False


def append_ledgers(
    report: dict[str, Any],
    report_sha256: str,
    *,
    run_path: Path,
    decision_path: Path,
) -> dict[str, bool]:
    run_id = str(report["run_id"])
    run_reused = append_once(
        run_path,
        RUN_FIELDS,
        {
            "run_id": run_id,
            "protocol_sha256": report["protocol_sha256"],
            "execution_release_sha256": report["execution_release_sha256"],
            "implementation_git_head": report["implementation_git_head"],
            "code_bundle_sha256": report["code_bundle_sha256"],
            "input_snapshot_sha256": report["input_snapshot_sha256"],
            "run_started_at": report["run_started_at"],
            "run_finished_at": report["run_finished_at"],
            "direction_pass_count": report["direction_pass_count"],
            "adapted_gate_pass_count": report["adapted_gate_pass_count"],
            "formal_g1_v1_status": report["formal_g1_v1_status"],
            "determinism_pass": str(report["determinism_pass"]).lower(),
            "verdict": report["verdict"],
            "strategy_effective": report["strategy_effective"],
            "production_authorization": "none",
            "effect_report_sha256": report_sha256,
        },
        run_id,
    )
    decision_reused = True
    for row in report["candidates"]:
        decision_id = f"{run_id}-{row['candidate']}"
        reused = append_once(
            decision_path,
            DECISION_FIELDS,
            {
                "decision_id": decision_id,
                "run_id": run_id,
                "candidate": row["candidate"],
                "direction_pass": str(row["direction"]["direction_pass"]).lower(),
                "oos_effect_read": str(row["oos_effect_read"]).lower(),
                "adapted_gate_decision": row["adapted_gate_decision"],
                "failed_gates": "|".join(row["failed_gates"]),
                "formal_g1_v1_status": row["formal_g1_v1_status"],
                "production_authorization": "none",
                "effect_report_sha256": report_sha256,
            },
            decision_id,
        )
        decision_reused = decision_reused and reused
    return {"run": run_reused, "decisions": decision_reused}
