"""重判的复现预检、精确 scope、逐字批准转录、一次性认领与单次执行（协议 v2 §5）。工具从不自造批准。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS, sha256_file
from shaiwei.research.g1_calibration.ledger_view import complete_rows
from shaiwei.research.g1_calibration.scope import SNAPSHOT_PY, _run, directory_fingerprint
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2, RejudgeIdentity, load_rejudge_protocol

CONTROL_ROOT = PROJECT_ROOT / "data" / "control" / "g1-v2-rejudge"
_HEX64 = r"^[0-9a-f]{64}$"


class RejudgeScopeError(RuntimeError):
    pass


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Ledgers(_Frozen):
    experiments_rows: int = Field(ge=0)
    rejudge_rows: Literal[0]
    admissions_v2_rows: Literal[0]
    factor_admissions_v1_sha256: str = Field(pattern=_HEX64)


class RejudgeScope(_Frozen):
    schema_version: Literal["g1-v2-rejudge-scope-v1"]
    protocol_id: Literal["g1-v2-rejudge-v2"]
    protocol_config_sha256: str = Field(pattern=_HEX64)
    protocol_document_sha256: str = Field(pattern=_HEX64)
    spec_sha256: str = Field(pattern=_HEX64)
    execution_id: str = Field(pattern=r"^g1rj-[0-9a-f]{12}-\d{8}T\d{6}Z$")
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    image: str = Field(pattern=r"^shaiwei:g1-calibration-[0-9a-f]{12}$")
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=_HEX64)
    data_snapshot_sha256: str = Field(pattern=_HEX64)
    qlib_bin_sha256: str = Field(pattern=_HEX64)
    units: Literal[21]
    precheck_report_path: str
    precheck_report_sha256: str = Field(pattern=_HEX64)
    ledgers: Ledgers
    prepared_at: str


class Envelope(_Frozen):
    scope_sha256: str = Field(pattern=_HEX64)
    scope: RejudgeScope


def scope_hash(scope: RejudgeScope) -> str:
    return hashlib.sha256(json.dumps(scope.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def approval_text(envelope: Envelope) -> str:
    return (
        f"批准 g1-v2 历史候选重判正式执行：以 scope {envelope.scope_sha256} 对镜像 {envelope.scope.image} 仅执行一次 g1-v2-rejudge-v2 "
        "全部 21 个因子定义（先过复现门）；结果只记 factor_admissions_v2，不入因子库，不写 v1 准入账本，不授权其他生产或研究动作。"
    )


def ledger_state(*, experiments: Path = EXPERIMENTS, admissions_v2: Path = FACTOR_ADMISSIONS_V2, admissions_v1: Path = FACTOR_ADMISSIONS) -> dict[str, object]:
    rows = complete_rows(experiments)
    rejudge = sum(json.loads(row["params_json"]).get("attempt_stage") == "g1_v2_rejudge" for row in rows)
    return {"experiments_rows": len(rows), "rejudge_rows": rejudge, "admissions_v2_rows": len(complete_rows(admissions_v2)),
            "factor_admissions_v1_sha256": sha256_file(admissions_v1)}


def reconstruct_all(settings: Settings, identity: RejudgeIdentity, research: object, *, tolerance: float | None = None) -> dict[str, list[object]]:
    """按冻结家族顺序重建全部 21 个定义并逐个过复现门（只算复现差值）。"""
    from shaiwei.research.g1_v2_rejudge.sources import (
        load_fundamental_inputs,
        load_moneyflow_inputs,
        rebuild_fundamental,
        rebuild_gp,
        rebuild_moneyflow,
    )

    config = identity.config
    tolerance = tolerance or config.reproduction_gate.max_abs_daily_difference
    minimum = settings.alphagen_benchmark.min_cross_section
    families = config.family_order
    result: dict[str, list[object]] = {}
    result[families[0]] = [rebuild_gp(c, research, min_cross_section=minimum, tolerance=tolerance) for c in config.families[families[0]]]  # type: ignore[arg-type]
    moneyflow = load_moneyflow_inputs(settings, research, PROJECT_ROOT / config.p1_source.raw_candidates_path, min_cross_section=minimum)  # type: ignore[arg-type]
    result[families[1]] = [rebuild_moneyflow(c, moneyflow, research, tolerance=tolerance) for c in config.families[families[1]]]  # type: ignore[arg-type]
    for family in families[2:]:
        inputs = load_fundamental_inputs(family, settings)
        result[family] = [rebuild_fundamental(family, c, inputs, tolerance=tolerance) for c in config.families[family]]
    return result


def _write_once(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def prepare(settings: Settings, *, image: str, precheck: Path) -> dict[str, str]:
    from shaiwei.ledger import ingest_snapshot_sha256
    from shaiwei.provenance import code_snapshot_sha256

    if _run(["git", "status", "--porcelain", "--untracked-files=no"]):
        raise RejudgeScopeError("tracked worktree is dirty")
    head = _run(["git", "rev-parse", "HEAD"])
    if head != _run(["git", "rev-parse", "origin/main"]):
        raise RejudgeScopeError("HEAD differs from origin/main")
    image_id = _run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
    image_snapshot = _run(["docker", "run", "--rm", "--network", "none", image, "python", "-c", SNAPSHOT_PY]).splitlines()[-1]
    if image_snapshot != code_snapshot_sha256() or not image.endswith(image_snapshot[:12]):
        raise RejudgeScopeError("image code snapshot differs from the pushed worktree")
    identity = load_rejudge_protocol(settings)
    report = json.loads(precheck.read_text(encoding="utf-8"))
    if report.get("scope") != "reproduction only; no g1-v2 statistic computed" or len(report["candidates"]) != 21:
        raise RejudgeScopeError("precheck report is not a complete reproduction-only report")
    scope = RejudgeScope(
        schema_version="g1-v2-rejudge-scope-v1", protocol_id=identity.config.protocol_id,
        protocol_config_sha256=identity.config_sha256, protocol_document_sha256=identity.document_sha256, spec_sha256=identity.spec_sha256,
        execution_id=f"g1rj-{head[:12]}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}", git_head=head, image=image, image_id=image_id,
        code_snapshot_sha256=image_snapshot, data_snapshot_sha256=ingest_snapshot_sha256(),
        qlib_bin_sha256=directory_fingerprint(settings.runtime.data_root / "qlib_bin"), units=21,
        precheck_report_path=precheck.resolve().relative_to(PROJECT_ROOT).as_posix(), precheck_report_sha256=sha256_file(precheck),
        ledgers=Ledgers.model_validate(ledger_state()), prepared_at=datetime.now(timezone.utc).isoformat(),
    )
    envelope = Envelope(scope_sha256=scope_hash(scope), scope=scope)
    _write_once(CONTROL_ROOT / "scopes" / f"{envelope.scope_sha256}.scope.json", envelope.model_dump(mode="json"))
    return {"status": "SCOPE_PREPARED_NOT_APPROVED", "scope_sha256": envelope.scope_sha256, "approval_text": approval_text(envelope)}


def load_envelope(scope_sha: str, root: Path = CONTROL_ROOT) -> Envelope:
    envelope = Envelope.model_validate_json((root / "scopes" / f"{scope_sha}.scope.json").read_text(encoding="utf-8"))
    if envelope.scope_sha256 != scope_sha or scope_hash(envelope.scope) != scope_sha:
        raise RejudgeScopeError("scope file does not hash to its declared identity")
    return envelope


def record_approval(scope_sha: str, text: str, root: Path = CONTROL_ROOT) -> dict[str, str]:
    envelope = load_envelope(scope_sha, root)
    if text != approval_text(envelope):
        raise RejudgeScopeError("approval text is not the exact verbatim text for this scope")
    try:
        _write_once(root / "approvals" / f"{scope_sha}.approval.json", {"scope_sha256": scope_sha, "approval_text": text})
    except FileExistsError as error:
        raise RejudgeScopeError("approval already recorded for this scope") from error
    return {"status": "APPROVAL_RECORDED", "scope_sha256": scope_sha}


def load_approved(scope_sha: str, root: Path = CONTROL_ROOT) -> Envelope:
    envelope = load_envelope(scope_sha, root)
    approval = json.loads((root / "approvals" / f"{scope_sha}.approval.json").read_text(encoding="utf-8"))
    if approval != {"scope_sha256": scope_sha, "approval_text": approval_text(envelope)}:
        raise RejudgeScopeError("approval does not match this scope verbatim")
    return envelope


def verify(envelope: Envelope, identity: RejudgeIdentity, *, code: str, data: str, qlib: str, ledgers: dict[str, object]) -> None:
    scope = envelope.scope
    checks = {
        "protocol config": (identity.config_sha256, scope.protocol_config_sha256), "protocol document": (identity.document_sha256, scope.protocol_document_sha256),
        "spec": (identity.spec_sha256, scope.spec_sha256), "code": (code, scope.code_snapshot_sha256), "data": (data, scope.data_snapshot_sha256),
        "qlib_bin": (qlib, scope.qlib_bin_sha256), "re-judge rows": (ledgers["rejudge_rows"], 0), "admissions v2 rows": (ledgers["admissions_v2_rows"], 0),
        "factor_admissions v1": (ledgers["factor_admissions_v1_sha256"], scope.ledgers.factor_admissions_v1_sha256),
    }
    drift = [name for name, (actual, expected) in checks.items() if actual != expected]
    if drift:
        raise RejudgeScopeError(f"execution preconditions drifted from the approved scope: {drift}")


def claim(directory: Path, scope_sha: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    try:
        _write_once(directory / "claim.json", {"scope_sha256": scope_sha, "claimed_at": datetime.now(timezone.utc).isoformat(), "state": "MAY_HAVE_WRITTEN"})
    except FileExistsError as error:
        raise RejudgeScopeError("this re-judge execution was already claimed; a rerun needs a new scope and approval") from error


def execute(scope_sha: str, *, settings: Settings | None = None, control: Path = CONTROL_ROOT, facts: Callable[[Settings], dict[str, str]] | None = None,
            loader: Callable[[Settings, RejudgeIdentity], tuple[object, dict[str, list[object]]]] | None = None, roots=None) -> dict[str, object]:
    from shaiwei.research.g1_v2 import load_spec
    from shaiwei.research.g1_v2_rejudge.evaluate import RejudgeContext, run_rejudge
    from shaiwei.research.g1_v2_rejudge.judge import rejudge_roots

    settings = settings or load()
    identity = load_rejudge_protocol(settings)
    envelope = load_approved(scope_sha, control)
    roots = roots or rejudge_roots(settings, envelope.scope.execution_id)
    if facts is None:
        from shaiwei.research.g1_calibration.execute import live_facts as facts  # noqa: N813
    live = facts(settings)
    verify(envelope, identity, code=live["code_snapshot"], data=live["data_snapshot"], qlib=live["qlib_fingerprint"],
           ledgers=ledger_state(experiments=roots.experiments, admissions_v2=roots.admissions))
    claim(roots.data, scope_sha)
    if loader is None:
        loader = _live_loader
    context_parts, reconstructions = loader(settings, identity)
    ctx = RejudgeContext(settings=settings, identity=identity, spec=load_spec(settings).spec, code_hash=live["code_snapshot"],
                         data_hash=live["data_snapshot"], **context_parts)  # type: ignore[arg-type]
    from shaiwei.research.g1_v2_rejudge.sources import write_reproduction_report

    write_reproduction_report(roots.reports / "reproduction.json", [item for items in reconstructions.values() for item in items])
    summary = run_rejudge(ctx, roots, reconstructions)
    return {"execution_id": envelope.scope.execution_id, "counts": summary["counts"]}


def _live_loader(settings: Settings, identity: RejudgeIdentity) -> tuple[dict[str, object], dict[str, list[object]]]:
    from shaiwei.research.g1_pipeline import build_baseline_windows, load_research_data

    research = load_research_data(settings)
    baselines = build_baseline_windows(settings, research.labels)
    return {"research": research, "baselines": baselines}, reconstruct_all(settings, identity, research)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pre = commands.add_parser("precheck", help="复现预检：只算复现差值，不算任何 g1-v2 统计量")
    pre.add_argument("--output", type=Path, required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--image", required=True)
    prep.add_argument("--precheck", type=Path, required=True)
    approve = commands.add_parser("record-approval")
    approve.add_argument("--scope", required=True)
    approve.add_argument("--text", required=True)
    check = commands.add_parser("check-image")
    check.add_argument("--scope", required=True)
    run = commands.add_parser("execute")
    run.add_argument("--scope", required=True)
    args = parser.parse_args(argv)
    settings = load()
    if args.command == "precheck":
        from shaiwei.research.g1_pipeline import load_research_data

        allowed = (PROJECT_ROOT / "logs" / "g1-v2" / "precheck").resolve()
        if not args.output.resolve().is_relative_to(allowed) or args.output.exists():
            raise SystemExit(f"precheck output must be a new file under {allowed}")
        identity = load_rejudge_protocol(settings)
        from shaiwei.research.g1_v2_rejudge.sources import write_reproduction_report

        items = reconstruct_all(settings, identity, load_research_data(settings))
        report = write_reproduction_report(args.output, [item for group in items.values() for item in group])
        print(json.dumps({c["family"]: c["status"] for c in report["candidates"]}, ensure_ascii=False))
        return 0
    if args.command == "prepare":
        result: object = prepare(settings, image=args.image, precheck=args.precheck)
    elif args.command == "record-approval":
        result = record_approval(args.scope, args.text)
    elif args.command == "check-image":
        envelope = load_approved(args.scope)
        if _run(["docker", "image", "inspect", "--format", "{{.Id}}", envelope.scope.image]) != envelope.scope.image_id:
            raise SystemExit("local image id differs from the approved scope")
        print(envelope.scope.image)
        return 0
    else:
        result = execute(args.scope, settings=settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
