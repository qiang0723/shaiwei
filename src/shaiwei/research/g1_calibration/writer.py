"""标定输出的唯一写入口（协议 §8 硬隔离）。

只写：标定数据目录、标定报告目录、实验总账中的标定家族行、`ledger/g1_calibration_runs.csv`。
正式准入账本、`logs/g1/`、因子库与正式 G1 研究目录一律拒写；每份证据带顶层
`admission_scope: NOT_FOR_ADMISSION`，正式裁判（extra="forbid"）读到即校验失败。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ledger import (
    EXPERIMENTS,
    FACTOR_ADMISSIONS,
    G1_CALIBRATION_RUNS,
    append_experiment,
    append_g1_calibration_run,
    portable_artifact_path,
    sha256_file,
)
from shaiwei.research.g1_calibration.protocol import ADMISSION_SCOPE, ProtocolIdentity
from shaiwei.research.g1_pipeline import _write_json_once

DATA_DIRNAME = "g1-calibration-v1"


class IsolationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutputRoots:
    data: Path
    reports: Path
    experiments: Path
    runs: Path
    forbidden: tuple[Path, ...]


def output_roots(
    settings: Settings,
    execution_id: str,
    *,
    experiments: Path = EXPERIMENTS,
    runs: Path = G1_CALIBRATION_RUNS,
    data_root: Path | None = None,
    reports_root: Path | None = None,
) -> OutputRoots:
    research = settings.runtime.data_root / "research"
    forbidden = (
        FACTOR_ADMISSIONS.resolve(),
        (PROJECT_ROOT / "logs" / "g1").resolve(),
        (research / "factor_library").resolve(),
        (research / "g1").resolve(),
    )
    roots = OutputRoots(
        data=(data_root or research / DATA_DIRNAME) / execution_id,
        reports=(reports_root or PROJECT_ROOT / "logs" / "g1-calibration") / execution_id,
        experiments=experiments,
        runs=runs,
        forbidden=forbidden,
    )
    for path in (roots.data, roots.reports, roots.experiments, roots.runs):
        _refuse_forbidden(path, roots)
    if roots.runs.resolve() == roots.experiments.resolve():
        raise IsolationError("calibration runs ledger must be separate from the experiment ledger")
    return roots


def _refuse_forbidden(path: Path, roots: OutputRoots) -> None:
    resolved = path.resolve()
    for forbidden in roots.forbidden:
        if resolved == forbidden or resolved.is_relative_to(forbidden):
            raise IsolationError(f"calibration output may not touch {forbidden}")


def guarded(path: Path, root: Path, roots: OutputRoots) -> Path:
    if not path.resolve().is_relative_to(root.resolve()):
        raise IsolationError(f"{path} escapes the calibration output root {root}")
    _refuse_forbidden(path, roots)
    return path


def write_json_once(path: Path, document: dict[str, object], *, root: Path, roots: OutputRoots) -> Path:
    return _write_json_once(guarded(path, root, roots), document)


def write_factor_panel(path: Path, factor: pd.Series, labels: pd.Series, *, roots: OutputRoots) -> Path:
    """R1/R2 面板含未来信息：只落标定目录，且 parquet 元数据带 NOT_FOR_ADMISSION 标记。"""
    guarded(path, roots.data, roots)
    panel = pd.concat([factor.rename("factor"), labels.rename("label")], axis=1, join="inner").reset_index()
    if panel.empty:
        raise IsolationError("calibration factor panel is empty")
    table = pa.Table.from_pandas(panel, preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), b"admission_scope": ADMISSION_SCOPE.encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if not pq.read_table(path).equals(table):
            raise IsolationError(f"existing immutable calibration panel differs: {path}")
        return path
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        pq.write_table(table, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def experiment_id(protocol: ProtocolIdentity, family: str, seed: int | None, code_hash: str, data_hash: str) -> str:
    key = f"{protocol.config.protocol_id}|{family}|{seed}|{code_hash}|{data_hash}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _existing_row(path: Path, key: str, value: str) -> dict[str, str] | None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row[key] == value]
    if len(rows) > 1:
        raise IsolationError(f"duplicate {key} in {path.name}: {value}")
    return rows[0] if rows else None


def record_experiment(
    roots: OutputRoots,
    *,
    experiment: str,
    seed: int | None,
    code_hash: str,
    data_hash: str,
    formula: str,
    params: dict[str, object],
    result: dict[str, object],
    discovery: str,
) -> None:
    """每次评估（含失败）各记一行实验总账，计入本格 N；同绑定复跑只复用、不追加第二行。"""
    params = {**params, "admission_scope": ADMISSION_SCOPE}
    if existing := _existing_row(roots.experiments, "experiment_id", experiment):
        same = (
            existing["feature_or_formula"] == formula
            and existing["code_sha256"] == code_hash
            and existing["data_snapshot_sha256"] == data_hash
            and json.loads(existing["params_json"]) == params
        )
        previous = json.loads(existing["result_json"]).get("selection_sharpe")
        current = result.get("selection_sharpe")
        if not same or (previous is None) != (current is None) or (
            previous is not None and not math.isclose(float(previous), float(current), rel_tol=1e-12, abs_tol=1e-15)  # type: ignore[arg-type]
        ):
            raise IsolationError(f"existing calibration experiment differs: {experiment}")
        return
    # 与 g1_pipeline 相同走 append_experiment：g1-v1 复杂度绑定要求 params_json.expression_tokens，
    # 而 append_experiment_once 的敏感词过滤会误拒“token”；幂等由上面的既有行比对保证。
    append_experiment(
        path=roots.experiments,
        experiment_id=experiment,
        parent_experiment_id="",
        ts=datetime.now(timezone.utc).isoformat(),
        candidate_source="G1-calibration",
        model_or_engine=f"{params['route']} {params['construction']}",
        engine_version="g1-calibration-v1",
        seed="" if seed is None else seed,
        prompt_hash="",
        code_sha256=code_hash,
        data_snapshot_sha256=data_hash,
        feature_or_formula=formula,
        params_json=params,
        train_period=discovery,
        valid_period="W1-W6 + frozen stress periods",
        result_json=result,
        admitted=False,
        reject_reason="NOT_FOR_ADMISSION calibration control; judged only in g1_calibration_runs",
    )


def record_verdict(roots: OutputRoots, row: dict[str, object]) -> bool:
    """同一 run_id 已存在即复用，不改写；正式准入账本永不出现在此路径。"""
    if _existing_row(roots.runs, "run_id", str(row["run_id"])):
        return False
    return append_g1_calibration_run(path=roots.runs, **row)


def artifact(path: Path) -> tuple[str, str]:
    return portable_artifact_path(path), sha256_file(path)
