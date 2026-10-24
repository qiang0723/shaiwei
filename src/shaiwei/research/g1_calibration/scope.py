"""第 4 步正式执行的精确 scope、逐字批准转录与执行前复核（协议 §10 第 4 步）。

`prepare` 在宿主读取 git/镜像/数据/账本元数据并写 scope（不运行评估）；`record-approval` 只转录用户逐字回复，
文本与 `approval_text(scope)` 不完全一致即拒绝——工具从不自造批准。`verify_for_execution` 在断网容器内逐项复核。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS, G1_CALIBRATION_RUNS, sha256_file
from shaiwei.research.g1_calibration.ledger_view import IsolationError, complete_rows
from shaiwei.research.g1_calibration.protocol import ProtocolError, ProtocolIdentity, load_protocol

CONTROL_ROOT = PROJECT_ROOT / "data" / "control" / "g1-calibration-v1"
SNAPSHOT_PY = "from shaiwei.provenance import code_snapshot_sha256; print(code_snapshot_sha256())"
_HEX40, _HEX64 = r"^[0-9a-f]{40}$", r"^[0-9a-f]{64}$"


class ScopeError(RuntimeError):
    pass


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LedgerBaseline(_Frozen):
    experiments_rows: int = Field(ge=0)
    calibration_family_rows: Literal[0]
    calibration_runs_rows: Literal[0]
    factor_admissions_sha256: str = Field(pattern=_HEX64)


class ReleaseScope(_Frozen):
    schema_version: Literal["g1-calibration-release-scope-v1"]
    protocol_id: Literal["g1-positive-control-v1"]
    protocol_config_sha256: str = Field(pattern=_HEX64)
    protocol_document_sha256: str = Field(pattern=_HEX64)
    execution_id: str = Field(pattern=r"^g1cal-[0-9a-f]{12}-\d{8}T\d{6}Z$")
    git_head: str = Field(pattern=_HEX40)
    image: str = Field(pattern=r"^shaiwei:g1-calibration-[0-9a-f]{12}$")
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=_HEX64)
    data_snapshot_sha256: str = Field(pattern=_HEX64)
    qlib_bin_sha256: str = Field(pattern=_HEX64)
    noise_seeds_per_control: int = Field(ge=1)
    evaluations: int = Field(ge=1)
    budget_max_hours: float = Field(gt=0)
    pilot_timing_path: str
    pilot_timing_sha256: str = Field(pattern=_HEX64)
    pilot_projected_hours: float = Field(gt=0)
    ledgers: LedgerBaseline
    prepared_at: str


class ScopeEnvelope(_Frozen):
    scope_sha256: str = Field(pattern=_HEX64)
    scope: ReleaseScope


class Approval(_Frozen):
    schema_version: Literal["g1-calibration-approval-v1"]
    scope_sha256: str = Field(pattern=_HEX64)
    approval_text: str


def scope_hash(scope: ReleaseScope) -> str:
    canonical = json.dumps(scope.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def approval_text(envelope: ScopeEnvelope) -> str:
    scope = envelope.scope
    return (
        f"批准 G1 正控正式执行：以 scope {envelope.scope_sha256} 对镜像 {scope.image} 仅执行一次 g1-positive-control-v1 "
        f"全部 {scope.evaluations} 次评估（N1/N2 各 {scope.noise_seeds_per_control} 种子）；NOT_FOR_ADMISSION，"
        "不写正式准入账本，不授权其他生产或研究动作。"
    )


def directory_fingerprint(root: Path) -> str:
    """qlib_bin（G0 冻结缓存）按相对路径+内容逐文件哈希；任何增删改都会改变指纹。"""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + sha256_file(path).encode() + b"\n")
    return digest.hexdigest()


def ledger_baseline(protocol: ProtocolIdentity, *, experiments: Path = EXPERIMENTS, runs: Path = G1_CALIBRATION_RUNS,
                    admissions: Path = FACTOR_ADMISSIONS) -> dict[str, object]:
    rows = complete_rows(experiments)
    family = f"{protocol.config.family}/"
    calibration = sum(json.loads(row["params_json"]).get("g1_research_family", "").startswith(family) for row in rows)
    return {
        "experiments_rows": len(rows),
        "calibration_family_rows": calibration,
        "calibration_runs_rows": len(complete_rows(runs)),
        "factor_admissions_sha256": sha256_file(admissions),
    }


def choose_noise_seeds(protocol: ProtocolIdentity, projections: dict[str, dict[str, float]]) -> int:
    """协议 §4：超预算时只按冻结削减顺序减 N1/N2，从不减 R1。"""
    config = protocol.config
    order = [len(config.routes["N1"].seed_values()), *(step["N1"] for step in config.budget.reduction_order)]
    for seeds in order:
        if projections[str(seeds)]["projected_hours"] <= config.budget.max_hours:
            return seeds
    raise ScopeError("even the smallest frozen noise budget exceeds max_hours; a new protocol is required")


def _run(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300).stdout.strip()


def _write_once(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def prepare(settings: Settings, *, image: str, pilot_timing: Path) -> dict[str, str]:
    if _run(["git", "status", "--porcelain", "--untracked-files=no"]):
        raise ScopeError("tracked worktree is dirty")
    head = _run(["git", "rev-parse", "HEAD"])
    if head != _run(["git", "rev-parse", "origin/main"]):
        raise ScopeError("HEAD differs from origin/main; the formal image must come from a pushed commit")
    image_id = _run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
    image_snapshot = _run(["docker", "run", "--rm", "--network", "none", image, "python", "-c", SNAPSHOT_PY]).splitlines()[-1]
    from shaiwei.ledger import ingest_snapshot_sha256
    from shaiwei.provenance import code_snapshot_sha256

    if image_snapshot != code_snapshot_sha256() or not image.endswith(image_snapshot[:12]):
        raise ScopeError("image code snapshot differs from the pushed worktree")
    protocol = load_protocol(settings)
    timing = json.loads(pilot_timing.read_text(encoding="utf-8"))
    seeds = choose_noise_seeds(protocol, timing["projections"])
    scope = ReleaseScope(
        schema_version="g1-calibration-release-scope-v1",
        protocol_id=protocol.config.protocol_id,
        protocol_config_sha256=protocol.config_sha256,
        protocol_document_sha256=protocol.document_sha256,
        execution_id=f"g1cal-{head[:12]}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
        git_head=head,
        image=image,
        image_id=image_id,
        code_snapshot_sha256=image_snapshot,
        data_snapshot_sha256=ingest_snapshot_sha256(),
        qlib_bin_sha256=directory_fingerprint(settings.runtime.data_root / "qlib_bin"),
        noise_seeds_per_control=seeds,
        evaluations=int(timing["projections"][str(seeds)]["evaluations"]),
        budget_max_hours=protocol.config.budget.max_hours,
        pilot_timing_path=pilot_timing.resolve().relative_to(PROJECT_ROOT).as_posix(),
        pilot_timing_sha256=sha256_file(pilot_timing),
        pilot_projected_hours=float(timing["projections"][str(seeds)]["projected_hours"]),
        ledgers=LedgerBaseline.model_validate(ledger_baseline(protocol)),
        prepared_at=datetime.now(timezone.utc).isoformat(),
    )
    envelope = ScopeEnvelope(scope_sha256=scope_hash(scope), scope=scope)
    _write_once(CONTROL_ROOT / "scopes" / f"{envelope.scope_sha256}.scope.json", envelope.model_dump(mode="json"))
    return {"status": "SCOPE_PREPARED_NOT_APPROVED", "scope_sha256": envelope.scope_sha256, "approval_text": approval_text(envelope)}


def load_envelope(scope_sha: str, root: Path = CONTROL_ROOT) -> ScopeEnvelope:
    envelope = ScopeEnvelope.model_validate_json((root / "scopes" / f"{scope_sha}.scope.json").read_text(encoding="utf-8"))
    if envelope.scope_sha256 != scope_sha or scope_hash(envelope.scope) != scope_sha:
        raise ScopeError("scope file does not hash to its declared identity")
    return envelope


def record_approval(scope_sha: str, text: str, root: Path = CONTROL_ROOT) -> dict[str, str]:
    envelope = load_envelope(scope_sha, root)
    if text != approval_text(envelope):
        raise ScopeError("approval text is not the exact verbatim text for this scope")
    approval = Approval(schema_version="g1-calibration-approval-v1", scope_sha256=scope_sha, approval_text=text)
    try:
        _write_once(root / "approvals" / f"{scope_sha}.approval.json", approval.model_dump(mode="json"))
    except FileExistsError as error:
        raise ScopeError("approval already recorded for this scope") from error
    return {"status": "APPROVAL_RECORDED", "scope_sha256": scope_sha}


def load_approved(scope_sha: str, root: Path = CONTROL_ROOT) -> ScopeEnvelope:
    envelope = load_envelope(scope_sha, root)
    approval = Approval.model_validate_json((root / "approvals" / f"{scope_sha}.approval.json").read_text(encoding="utf-8"))
    if approval.scope_sha256 != scope_sha or approval.approval_text != approval_text(envelope):
        raise ScopeError("approval does not match this scope verbatim")
    return envelope


def verify_for_execution(
    envelope: ScopeEnvelope,
    protocol: ProtocolIdentity,
    *,
    code_snapshot: str,
    data_snapshot: str,
    qlib_fingerprint: str,
    baseline: dict[str, object],
) -> None:
    scope = envelope.scope
    checks = {
        "protocol config": (protocol.config_sha256, scope.protocol_config_sha256),
        "protocol document": (protocol.document_sha256, scope.protocol_document_sha256),
        "code snapshot": (code_snapshot, scope.code_snapshot_sha256),
        "data snapshot": (data_snapshot, scope.data_snapshot_sha256),
        "qlib_bin": (qlib_fingerprint, scope.qlib_bin_sha256),
        "factor_admissions": (baseline["factor_admissions_sha256"], scope.ledgers.factor_admissions_sha256),
        "calibration family rows": (baseline["calibration_family_rows"], 0),
        "calibration runs rows": (baseline["calibration_runs_rows"], 0),
    }
    drift = [name for name, (actual, expected) in checks.items() if actual != expected]
    if int(baseline["experiments_rows"]) < scope.ledgers.experiments_rows:  # type: ignore[arg-type]
        drift.append("experiments ledger shrank")
    if drift:
        raise ScopeError(f"execution preconditions drifted from the approved scope: {drift}")


def check_image(scope_sha: str, root: Path = CONTROL_ROOT) -> str:
    """宿主预检：已逐字批准，且本地镜像 ID 与 scope 一致；返回镜像标签给 compose。"""
    envelope = load_approved(scope_sha, root)
    if _run(["docker", "image", "inspect", "--format", "{{.Id}}", envelope.scope.image]) != envelope.scope.image_id:
        raise ScopeError("local image id differs from the approved scope")
    return envelope.scope.image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--image", required=True)
    prep.add_argument("--pilot-timing", type=Path, required=True)
    approve = commands.add_parser("record-approval")
    approve.add_argument("--scope", required=True)
    approve.add_argument("--text", required=True)
    check = commands.add_parser("check-image")
    check.add_argument("--scope", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result: object = prepare(load(), image=args.image, pilot_timing=args.pilot_timing)
        elif args.command == "record-approval":
            result = record_approval(args.scope, args.text)
        else:
            print(check_image(args.scope))
            return 0
    except (ScopeError, ProtocolError, IsolationError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"{type(error).__name__}: {error}") from error
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
