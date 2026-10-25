"""重判独立审计：不加载 qlib/torch，只读证据、报告与账本，逐个按 g1-v2 重判并比对 v2 准入账本与汇总。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS, sha256_file
from shaiwei.research.g1_calibration.ledger_view import complete_rows
from shaiwei.research.g1_v2 import load_spec
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2, load_rejudge_protocol
from shaiwei.research.g1_v2_rejudge.release import CONTROL_ROOT, load_approved

AUDIT_ROOT = PROJECT_ROOT / "logs" / "g1-v2-audit"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def audit(execution_id: str, *, settings: Settings, data_dir: Path, reports_dir: Path, control_root: Path = CONTROL_ROOT,
          experiments: Path = EXPERIMENTS, admissions_v2: Path = FACTOR_ADMISSIONS_V2, admissions_v1: Path = FACTOR_ADMISSIONS,
          identity=None) -> dict[str, object]:
    from shaiwei.research.g1_v2_rejudge.judge import RejudgeRoots, judge_unit

    findings: list[str] = []
    identity = identity or load_rejudge_protocol(settings, verify_artifacts=False)
    claim = json.loads((data_dir / "claim.json").read_text(encoding="utf-8"))
    envelope = load_approved(claim["scope_sha256"], control_root)
    summary = json.loads((reports_dir / "summary.json").read_text(encoding="utf-8"))
    if envelope.scope.execution_id != execution_id or summary["execution_id"] != execution_id:
        findings.append("execution id differs between scope, claim and summary")
    if sha256_file(admissions_v1) != envelope.scope.ledgers.factor_admissions_v1_sha256:
        findings.append("factor_admissions (g1-v1) changed")
    for name, actual, expected in (("protocol config", summary["protocol_config_sha256"], identity.config_sha256),
                                   ("spec", summary["spec_sha256"], identity.spec_sha256),
                                   ("code", summary["code_snapshot_sha256"], envelope.scope.code_snapshot_sha256),
                                   ("data", summary["data_snapshot_sha256"], envelope.scope.data_snapshot_sha256)):
        if actual != expected:
            findings.append(f"{name} mismatch")
    rows = [row for row in complete_rows(experiments) if json.loads(row["params_json"]).get("attempt_stage") == "g1_v2_rejudge"]
    evaluated = [u for u in summary["units"] if u["status"] != "NOT_REEVALUATED"]
    if len(rows) != len(evaluated) or {r["experiment_id"] for r in rows} != {u["experiment_id"] for u in evaluated}:
        findings.append(f"re-judge experiment rows {len(rows)} differ from evaluated units {len(evaluated)}")
    decisions = {row["candidate_experiment_id"]: row for row in complete_rows(admissions_v2)}
    ctx = SimpleNamespace(settings=settings, identity=identity, spec=load_spec(settings).spec)  # 判定只需这三项，不载入研究数据
    roots = RejudgeRoots(data=data_dir, reports=reports_dir, experiments=experiments, admissions=admissions_v2)
    recomputed: dict[str, int] = {"PASS": 0, "REJECT": 0, "NOT_REEVALUATED": 0, "EVIDENCE_ERROR": 0}
    for unit in summary["units"]:
        if unit["status"] in {"NOT_REEVALUATED", "EVIDENCE_ERROR"}:
            recomputed[unit["status"]] += 1
            continue
        report_path = _path(unit["report_path"])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        evidence_path = _path(report["bindings"]["evidence_path"])
        if sha256_file(evidence_path) != report["bindings"]["evidence_sha256"]:
            findings.append(f"{unit['experiment_id']}: evidence hash differs from its report")
            continue
        row = decisions.get(unit["experiment_id"])
        if row is None or row["report_sha256"] != sha256_file(report_path) or row["admitted"] != str(report["admitted"]).lower():
            findings.append(f"{unit['experiment_id']}: v2 admission row missing or differs from its report")
        again = judge_unit(ctx, roots, unit["family"], unit["experiment_id"], evidence_path, write=False)
        if again["status"] != report["status"] or again["failed_gates"] != report["failed_gates"]:
            findings.append(f"{unit['experiment_id']}: re-judged verdict differs from the report")
        recomputed[again["status"]] += 1
    if len(decisions) != recomputed["PASS"] + recomputed["REJECT"]:
        findings.append("v2 admission rows differ from judged units")
    if recomputed != summary["counts"]:
        findings.append("recomputed counts differ from the executed summary")
    return {"schema_version": 1, "execution_id": execution_id, "scope_sha256": envelope.scope_sha256,
            "status": "PASS" if not findings else "FAIL", "findings": findings, "recomputed_counts": recomputed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-id", required=True)
    args = parser.parse_args(argv)
    settings = load()
    result = audit(
        args.execution_id, settings=settings,
        data_dir=settings.runtime.data_root / "research" / "g1-v2-rejudge" / args.execution_id,
        reports_dir=PROJECT_ROOT / "logs" / "g1-v2" / args.execution_id,
    )
    target = AUDIT_ROOT / args.execution_id / "audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "recomputed_counts")}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
