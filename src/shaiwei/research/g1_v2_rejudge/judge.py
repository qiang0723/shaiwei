"""重判判定（协议 v2 §3.3–3.4）：按 v1 声明的多重检验家族在完整前缀快照上统计 N 与方差，调用 g1-v2 判定。

不依赖 qlib/torch，供正式执行与独立审计共用。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS, append_factor_admission, portable_artifact_path, sha256_file
from shaiwei.research.g1 import _verify_integrity_binding, family_trials
from shaiwei.research.g1_calibration.ledger_view import complete_rows, prefix_snapshot
from shaiwei.research.g1_v2 import G1EvidenceV2, evaluate_gates_v2, family_increment_irs
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2


def write_json_once(path: Path, document: dict[str, object]) -> Path:
    """排他创建；已存在则必须逐字节相同（同绑定复跑复用）。"""
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != payload:
            raise RejudgeIsolationError(f"existing immutable JSON differs: {path}") from None
    return path


class RejudgeIsolationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RejudgeRoots:
    data: Path
    reports: Path
    experiments: Path
    admissions: Path


def rejudge_roots(settings: Settings, execution_id: str, *, experiments: Path = EXPERIMENTS, admissions: Path = FACTOR_ADMISSIONS_V2,
                  data_root: Path | None = None, reports_root: Path | None = None) -> RejudgeRoots:
    roots = RejudgeRoots(
        data=(data_root or settings.runtime.data_root / "research" / "g1-v2-rejudge") / execution_id,
        reports=(reports_root or PROJECT_ROOT / "logs" / "g1-v2") / execution_id,
        experiments=experiments, admissions=admissions,
    )
    forbidden = (FACTOR_ADMISSIONS.resolve(), (PROJECT_ROOT / "logs" / "g1").resolve())
    for path in (roots.data, roots.reports, roots.experiments, roots.admissions):
        if any(path.resolve() == item or path.resolve().is_relative_to(item) for item in forbidden):
            raise RejudgeIsolationError(f"re-judge output may not touch {path}")
    return roots


def _existing(path: Path, key: str, value: str) -> dict[str, str] | None:
    rows = [row for row in complete_rows(path) if row[key] == value]
    return rows[0] if rows else None


def judge_unit(ctx: object, roots: RejudgeRoots, family: str, experiment: str, evidence_path: Path, *, write: bool = True) -> dict[str, object]:
    evidence = G1EvidenceV2.model_validate_json(evidence_path.read_text(encoding="utf-8"))
    families = tuple(ctx.identity.config.multiple_testing_families[family])
    related = tuple(f for f in families if f != family)
    with tempfile.TemporaryDirectory() as directory:  # 完整前缀快照：不读 scheduler 并发追加的半行
        snapshot = prefix_snapshot(roots.experiments, Path(directory))
        trials = family_trials(family, experiment, related_research_families=related, experiments_path=snapshot)
        irs = family_increment_irs(snapshot, families)
    _verify_integrity_binding(evidence, trials)
    gates, statistics = evaluate_gates_v2(ctx.settings, ctx.spec, evidence, trials, irs)
    failed = [name for name, gate in gates.items() if not gate["passed"]]
    evidence_sha = sha256_file(evidence_path)
    decision_id = hashlib.sha256(f"{experiment}{evidence_sha}{ctx.identity.spec_sha256}{trials.ledger_sha256}".encode()).hexdigest()[:12]
    report = {
        "schema_version": 1, "protocol_id": ctx.identity.config.protocol_id, "decision_id": decision_id,
        "status": "PASS" if not failed else "REJECT", "admitted": not failed, "failed_gates": failed,
        "candidate": {"experiment_id": experiment, "research_family": family, "multiple_testing_families": list(families)},
        "bindings": {"evidence_path": portable_artifact_path(evidence_path), "evidence_sha256": evidence_sha,
                     "spec_sha256": ctx.identity.spec_sha256, "experiment_ledger_sha256": trials.ledger_sha256},
        "gates": gates, "statistics": statistics,
    }
    if not write:
        return report
    report_path = write_json_once(roots.reports / family / f"{experiment}-{trials.ledger_sha256[:12]}.json", report)
    if not _existing(roots.admissions, "decision_id", decision_id):
        append_factor_admission(
            path=roots.admissions, decision_id=decision_id, candidate_experiment_id=experiment, research_family=family,
            evidence_sha256=evidence_sha, spec_sha256=ctx.identity.spec_sha256, experiment_ledger_sha256=trials.ledger_sha256,
            trial_count=trials.trial_count, valid_trial_sharpes=len(irs), report_path=portable_artifact_path(report_path),
            report_sha256=sha256_file(report_path), admitted=not failed, failed_gates="|".join(failed),
        )
    return {**report, "report_path": portable_artifact_path(report_path)}
