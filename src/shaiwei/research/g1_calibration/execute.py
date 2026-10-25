"""第 4 步正式执行入口（断网容器内）：复核已逐字批准的 scope → 一次性认领 → 单次全部评估。

认领文件先于任何评估以排他方式创建（MAY_HAVE_WRITTEN）；同一执行 ID 再次启动一律拒绝，重跑须新 scope 与新批准。
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from shaiwei.config import Settings, load
from shaiwei.ledger import FACTOR_ADMISSIONS
from shaiwei.research.g1_calibration.ledger_view import IsolationError
from shaiwei.research.g1_calibration.protocol import CONFIG_PATH, ProtocolError, ProtocolIdentity, load_protocol
from shaiwei.research.g1_calibration.scope import (
    ScopeError,
    control_root,
    directory_fingerprint,
    ledger_baseline,
    load_approved,
    verify_for_execution,
)
from shaiwei.research.g1_calibration.writer import OutputRoots, guarded, output_roots, write_json_once

Facts = Callable[[Settings], dict[str, str]]
ContextLoader = Callable[[Settings, ProtocolIdentity, dict[str, float]], object]


def live_facts(settings: Settings) -> dict[str, str]:
    from shaiwei.ledger import ingest_snapshot_sha256
    from shaiwei.provenance import code_snapshot_sha256

    return {
        "code_snapshot": code_snapshot_sha256(),
        "data_snapshot": ingest_snapshot_sha256(),
        "qlib_fingerprint": directory_fingerprint(settings.runtime.data_root / "qlib_bin"),
    }


def claim(roots: OutputRoots, scope_sha: str) -> Path:
    path = guarded(roots.data / "claim.json", roots.data, roots)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"scope_sha256": scope_sha, "claimed_at": datetime.now(timezone.utc).isoformat(), "state": "MAY_HAVE_WRITTEN"}
    try:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
            handle.write(json.dumps(document, sort_keys=True) + "\n")
    except FileExistsError as error:
        raise ScopeError("this execution was already claimed; a rerun needs a new scope and approval") from error
    return path


def execute(
    scope_sha: str,
    *,
    settings: Settings | None = None,
    protocol_path: Path = CONFIG_PATH,
    control: Path | None = None,
    roots: OutputRoots | None = None,
    facts: Facts = live_facts,
    context_loader: ContextLoader | None = None,
    admissions: Path = FACTOR_ADMISSIONS,
) -> dict[str, object]:
    from shaiwei.research.g1_calibration.runner import run_calibration

    settings = settings or load()
    protocol = load_protocol(settings, protocol_path)
    envelope = load_approved(scope_sha, control or control_root(protocol))
    if envelope.scope.protocol_id != protocol.config.protocol_id:
        raise ScopeError("approved scope belongs to a different protocol")
    roots = roots or output_roots(settings, envelope.scope.execution_id, protocol=protocol)
    if roots.data.name != envelope.scope.execution_id or roots.reports.name != envelope.scope.execution_id:
        raise ScopeError("output roots are not bound to the approved execution id")
    live = facts(settings)
    verify_for_execution(
        envelope,
        protocol,
        code_snapshot=live["code_snapshot"],
        data_snapshot=live["data_snapshot"],
        qlib_fingerprint=live["qlib_fingerprint"],
        baseline=ledger_baseline(protocol, experiments=roots.experiments, runs=roots.runs, admissions=admissions),
    )
    claim(roots, scope_sha)
    if context_loader is None:
        from shaiwei.research.g1_calibration.pilot import load_context

        context_loader = load_context
    timings: dict[str, float] = {}
    context = context_loader(settings, protocol, timings)
    document = run_calibration(context, roots, noise_seeds=envelope.scope.noise_seeds_per_control)  # type: ignore[arg-type]
    record = {
        "scope_sha256": scope_sha, "execution_id": envelope.scope.execution_id, "fixed_seconds": timings,
        "finished_at": datetime.now(timezone.utc).isoformat(), "summary_status": document["summary"]["status"],  # type: ignore[index]
    }
    write_json_once(roots.reports / "execution.json", record, root=roots.reports, roots=roots)
    return {"execution_id": envelope.scope.execution_id, "status": record["summary_status"],
            "terminal_state": document["summary"]["terminal_state"]}  # type: ignore[index]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True, help="已逐字批准的 scope SHA-256")
    parser.add_argument("--protocol", type=Path, default=CONFIG_PATH, help="冻结的正控协议配置（默认 v1）")
    args = parser.parse_args(argv)
    try:
        result = execute(args.scope, protocol_path=args.protocol)
    except (ScopeError, ProtocolError, IsolationError) as error:
        raise SystemExit(f"{type(error).__name__}: {error}") from error
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
