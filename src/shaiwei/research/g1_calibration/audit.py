"""独立审计（第 4 步）：不加载 qlib/torch，从落盘证据与账本重新判定，复算汇总与误放率上界，逐项比对执行结果。

只读一切被审对象；唯一输出是 `logs/g1-calibration-audit/<执行 ID>/audit.json`（排他创建，不覆盖）。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS, G1_CALIBRATION_RUNS, sha256_file
from shaiwei.research.g1_calibration.judge import INCREMENT_SCHEMA, judge
from shaiwei.research.g1_calibration.ledger_view import complete_rows
from shaiwei.research.g1_calibration.protocol import ADMISSION_SCOPE, CONFIG_PATH, ProtocolIdentity, load_protocol
from shaiwei.research.g1_calibration.scope import CONTROL_ROOT, control_root, load_approved
from shaiwei.research.g1_calibration.summary import UnitOutcome, summarize

AUDIT_ROOT = PROJECT_ROOT / "logs" / "g1-calibration-audit"


def audit_root(protocol: ProtocolIdentity) -> Path:
    """v1 → logs/g1-calibration-audit；v2 → logs/g1-calibration-v2-audit（与被审报告目录分开，审计不写被审对象）。"""
    return PROJECT_ROOT / f"{protocol.config.isolation.reports_dir}-audit"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _normalized(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def audit(
    execution_id: str,
    *,
    settings: Settings,
    protocol: ProtocolIdentity,
    data_dir: Path,
    reports_dir: Path,
    control_root: Path = CONTROL_ROOT,
    experiments: Path = EXPERIMENTS,
    runs: Path = G1_CALIBRATION_RUNS,
    admissions: Path = FACTOR_ADMISSIONS,
) -> dict[str, object]:
    findings: list[str] = []
    claim = json.loads((data_dir / "claim.json").read_text(encoding="utf-8"))
    envelope = load_approved(claim["scope_sha256"], control_root)
    scope = envelope.scope
    document = json.loads((reports_dir / "summary.json").read_text(encoding="utf-8"))
    if scope.execution_id != execution_id or document["execution_id"] != execution_id:
        findings.append("execution id differs between scope, claim and summary")
    for name, actual, expected in (
        ("protocol config", document["protocol_config_sha256"], protocol.config_sha256),
        ("protocol document", document["protocol_document_sha256"], protocol.document_sha256),
        ("code snapshot", document["code_snapshot_sha256"], scope.code_snapshot_sha256),
        ("data snapshot", document["data_snapshot_sha256"], scope.data_snapshot_sha256),
        ("factor_admissions unchanged", sha256_file(admissions), scope.ledgers.factor_admissions_sha256),
    ):
        if actual != expected:
            findings.append(f"{name} mismatch")
    family = f"{protocol.config.family}/"
    calibration_rows = [row for row in complete_rows(experiments) if json.loads(row["params_json"]).get("g1_research_family", "").startswith(family)]
    if len(calibration_rows) != scope.evaluations or len({row["experiment_id"] for row in calibration_rows}) != scope.evaluations:
        findings.append(f"calibration experiment rows {len(calibration_rows)} != approved evaluations {scope.evaluations}")
    if any(json.loads(row["params_json"]).get("admission_scope") != ADMISSION_SCOPE for row in calibration_rows):
        findings.append("calibration experiment row without NOT_FOR_ADMISSION")
    run_rows = {row["experiment_id"]: row for row in complete_rows(runs) if row["execution_id"] == execution_id}
    outcomes: list[UnitOutcome] = []
    for unit in document["units"]:
        base = {key: unit[key] for key in ("route", "strength", "seed", "cell_family", "experiment_id")}
        if unit["status"] != "JUDGED":
            outcomes.append(UnitOutcome(**base, status=unit["status"], error_type=unit["error_type"]))
            continue
        report_path = _path(unit["report_path"])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        row = run_rows.get(unit["experiment_id"])
        evidence_path = _path(report["bindings"]["evidence_path"])
        if row is None or row["report_sha256"] != sha256_file(report_path):
            findings.append(f"{unit['experiment_id']}: calibration ledger row missing or report hash differs")
        if sha256_file(evidence_path) != report["bindings"]["evidence_sha256"]:
            findings.append(f"{unit['experiment_id']}: evidence hash differs from its report")
            continue
        verdict = judge(settings, protocol, evidence_path, experiments_path=experiments)
        recomputed = {"A_signal": verdict.layer_a, "B_transmission": verdict.layer_b, "main": verdict.main}
        if recomputed != report["layers"] or list(verdict.failed_main) != report["failed_main_gates"]:
            findings.append(f"{unit['experiment_id']}: re-judged layers differ from the report")
        if verdict.cell_trials_sha256 != report["bindings"]["cell_trials_sha256"]:
            findings.append(f"{unit['experiment_id']}: cell trial set changed after judgment")
        if row is not None and row["main_pass"] != str(verdict.main).lower():
            findings.append(f"{unit['experiment_id']}: calibration ledger main_pass differs")
        stored = json.loads(evidence_path.read_text(encoding="utf-8"))
        if stored.get("admission_scope") != ADMISSION_SCOPE:
            findings.append(f"{unit['experiment_id']}: evidence lacks the NOT_FOR_ADMISSION marker")
        if stored.get("schema_version") != INCREMENT_SCHEMA:  # N3 增量证据不落面板
            tests = json.loads(_path(stored["integrity"]["test_report_path"]).read_text(encoding="utf-8"))
            if pq.read_schema(_path(tests["factor_panel_path"])).metadata.get(b"admission_scope") != ADMISSION_SCOPE.encode():
                findings.append(f"{unit['experiment_id']}: factor panel lacks the NOT_FOR_ADMISSION marker")
        outcomes.append(UnitOutcome(**base, status="JUDGED", main=verdict.main, layer_a=verdict.layer_a,
                                    layer_b=verdict.layer_b, failed_main=verdict.failed_main))
    if len(run_rows) != sum(unit["status"] == "JUDGED" for unit in document["units"]):
        findings.append("calibration ledger rows differ from judged units")
    recomputed_summary = summarize(protocol, outcomes, planned_noise_seeds=scope.noise_seeds_per_control)
    if _normalized(recomputed_summary) != _normalized(document["summary"]):
        findings.append("recomputed summary (terminal state / bound) differs from the executed summary")
    return {
        "schema_version": 1, "execution_id": execution_id, "scope_sha256": envelope.scope_sha256,
        "status": "PASS" if not findings else "FAIL", "findings": findings,
        "units_audited": len(outcomes), "recomputed_terminal_state": recomputed_summary["terminal_state"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--protocol", type=Path, default=CONFIG_PATH, help="冻结的正控协议配置（默认 v1）")
    args = parser.parse_args(argv)
    settings = load()
    protocol = load_protocol(settings, args.protocol)
    result = audit(
        args.execution_id,
        settings=settings,
        protocol=protocol,
        data_dir=settings.runtime.data_root / "research" / protocol.config.family / args.execution_id,
        reports_dir=PROJECT_ROOT / protocol.config.isolation.reports_dir / args.execution_id,
        control_root=control_root(protocol),
    )
    target = audit_root(protocol) / args.execution_id / "audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "units_audited", "recomputed_terminal_state")}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
