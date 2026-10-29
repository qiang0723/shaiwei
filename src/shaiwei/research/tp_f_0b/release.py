"""TP-F-0B in-image fixture report, scope preparation, single execution and the CLI. The tool never fabricates approval."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.g1_calibration.scope import SNAPSHOT_PY, _run
from shaiwei.research.tp_f_0b.audit import audit_once
from shaiwei.research.tp_f_0b.contract import ADDENDUM_DOCUMENT_SHA256, CONTROL_ROOT, DOCUMENT_SHA256, OUTPUT_ROOT, TPFError, TPFScope
from shaiwei.research.tp_f_0b.scope import (
    Envelope,
    Scope,
    _write_once,
    approval_text,
    data_facts,
    load_approved,
    record_approval,
    scope_hash,
    verify,
)

FIXTURE_ROOT = PROJECT_ROOT / "logs" / "tp-f-0b" / "fixture"


def fixture_report(output: Path) -> dict[str, Any]:
    from shaiwei.provenance import code_snapshot_sha256
    from shaiwei.research.tp_f_0b.fixture import fixture

    contract = TPFScope.load()
    report = {"schema_version": "tp-f-0b-fixture-report-v1", "protocol_sha256": contract.sha256,
              "addendum_sha256": contract.addendum_sha256, "code_snapshot_sha256": code_snapshot_sha256(), **fixture()}
    _write_once(output, report)
    return report


def prepare(*, image: str, fixture: Path, control: Path = CONTROL_ROOT,
            facts: Callable[[TPFScope], dict[str, Any]] = data_facts) -> dict[str, str]:
    from shaiwei.provenance import code_snapshot_sha256

    if _run(["git", "status", "--porcelain", "--untracked-files=no"]):
        raise TPFError("tracked worktree is dirty")
    head = _run(["git", "rev-parse", "HEAD"])
    if head != _run(["git", "rev-parse", "origin/main"]):
        raise TPFError("HEAD differs from origin/main")
    image_id = _run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
    image_snapshot = _run(["docker", "run", "--rm", "--network", "none", image, "python", "-c", SNAPSHOT_PY]).splitlines()[-1]
    if image_snapshot != code_snapshot_sha256() or not image.endswith(image_snapshot[:12]):
        raise TPFError("image code snapshot differs from the pushed worktree")
    contract = TPFScope.load()
    if not fixture.resolve().is_relative_to(FIXTURE_ROOT.resolve()):
        raise TPFError(f"fixture report must live under {FIXTURE_ROOT}")
    report = json.loads(fixture.read_text(encoding="utf-8"))
    frozen_cases = sum(len(rows) for rows in contract.document["adversarial_fixtures"].values() if isinstance(rows, list))
    if (report.get("fixture_pass") is not True or report.get("adversarial_cases") != frozen_cases
            or report.get("code_snapshot_sha256") != image_snapshot or report.get("addendum_sha256") != contract.addendum_sha256):
        raise TPFError("fixture report is not a passing in-image report for this code snapshot")
    scope = Scope(
        schema_version="tp-f-0b-scope-v1", protocol_id=contract.document["protocol_id"],
        protocol_sha256=contract.sha256, protocol_document_sha256=DOCUMENT_SHA256,
        addendum_sha256=contract.addendum_sha256, addendum_document_sha256=ADDENDUM_DOCUMENT_SHA256,
        execution_id=f"tpf0b-{head[:12]}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}", git_head=head, image=image,
        image_id=image_id, code_snapshot_sha256=image_snapshot, **facts(contract),
        fixture_report_path=fixture.resolve().relative_to(PROJECT_ROOT).as_posix(),
        fixture_report_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        prepared_at=datetime.now(timezone.utc).isoformat(),
    )
    envelope = Envelope(scope_sha256=scope_hash(scope), scope=scope)
    _write_once(control / "scopes" / f"{envelope.scope_sha256}.scope.json", envelope.model_dump(mode="json"))
    return {"status": "SCOPE_PREPARED_NOT_APPROVED", "scope_sha256": envelope.scope_sha256, "approval_text": approval_text(envelope)}


def execute(scope_sha: str, *, control: Path = CONTROL_ROOT, root: Path = PROJECT_ROOT, output_root: Path = OUTPUT_ROOT,
            facts: Callable[[TPFScope], dict[str, Any]] = data_facts, code: str | None = None,
            limits: dict[str, float] | None = None, alpha158: Callable[[], list[str]] | None = None) -> dict[str, Any]:
    from shaiwei.config import load
    from shaiwei.provenance import code_snapshot_sha256
    from shaiwei.research.tp_f_0b.profile import run_once
    from shaiwei.research.tp_f_0b.registry import alpha158_expressions

    envelope = load_approved(scope_sha, control)
    contract = TPFScope.load(root)
    verify(envelope, contract, code=code or code_snapshot_sha256(), facts=facts(contract))
    release = {"git_head": envelope.scope.git_head, "image": envelope.scope.image, "code_snapshot_sha256": envelope.scope.code_snapshot_sha256}
    return run_once(contract, scope_sha256=scope_sha, execution_id=envelope.scope.execution_id, release=release, root=root,
                    output_root=output_root, limits=limits or load().limit_rules.model_dump(), alpha158=alpha158 or alpha158_expressions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fixture", help="18 个全合成对抗 fixture（镜像内），写报告").add_argument("--output", type=Path, required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--image", required=True)
    prep.add_argument("--fixture", type=Path, required=True)
    approve = commands.add_parser("record-approval")
    approve.add_argument("--scope", required=True)
    approve.add_argument("--text", required=True)
    for name in ("check-image", "profile", "audit"):
        commands.add_parser(name).add_argument("--scope", required=True)
    args = parser.parse_args(argv)
    if args.command == "fixture":
        if not args.output.resolve().is_relative_to(FIXTURE_ROOT.resolve()) or args.output.exists():
            raise SystemExit(f"fixture output must be a new file under {FIXTURE_ROOT}")
        result: object = fixture_report(args.output)
    elif args.command == "prepare":
        result = prepare(image=args.image, fixture=args.fixture)
    elif args.command == "record-approval":
        result = record_approval(args.scope, args.text)
    elif args.command == "check-image":
        envelope = load_approved(args.scope)
        if _run(["docker", "image", "inspect", "--format", "{{.Id}}", envelope.scope.image]) != envelope.scope.image_id:
            raise SystemExit("local image id differs from the approved scope")
        print(envelope.scope.image)
        return 0
    elif args.command == "profile":
        result = execute(args.scope)
    else:
        result = audit_once(args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
