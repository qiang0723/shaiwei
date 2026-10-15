"""R2D 单次授权 scope 生成与批准转录（ADR 0016 §11 E2）。

只读宿主元数据（git、release state/audit 哈希、运行中旧容器 ID），不运行任何容器、不读 `.env`、不改变生产。
批准文件只转录用户逐字回复：文本与 `approval_text(scope_sha)` 不完全一致即拒绝；工具从不自造批准。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.config import PROJECT_ROOT
from shaiwei.r2d_authorized_start import check_binding
from shaiwei.r2d_execution_contract import (
    Approval,
    ContractError,
    ExecutionScope,
    ScopeEnvelope,
    approval_text,
    load_scope,
    scope_hash,
    write_once,
)
from shaiwei.r2d_metadata_environment import SecureEnvironment
from shaiwei.release_metadata import confined, sha256

SCOPE_DIR = ".release/r2d-executions/scopes"
APPROVAL_DIR = ".release/r2d-executions/approvals"


def default_compose_project(root: Path = PROJECT_ROOT) -> str:
    return root.name.lower()


def build_scope(root: Path, protocol_path: str, compose_project: str, env) -> ScopeEnvelope:
    """从冻结协议与当前只读元数据组装 scope；任何绑定不成立即拒绝，不写文件。"""
    path = confined(root, protocol_path)
    from shaiwei import r2d_release_guard as guard

    protocol = guard.load_protocol(path)
    git = env.git_state()
    if not git.get("head") or git.get("head") != git.get("origin_main"):
        raise ContractError("scope requires HEAD to equal the local origin/main")
    state_sha256, audit_sha256 = env.release_hashes()
    scope = ExecutionScope(
        schema_version="r2d-execution-scope-v1",
        action="START_CURRENT_ONCE",
        protocol_path=protocol_path,
        protocol_sha256=sha256(path),
        protocol=protocol.model_dump(mode="json"),
        git_head=git["head"],
        origin_main=git["origin_main"],
        state_sha256=state_sha256,
        audit_sha256=audit_sha256,
        legacy_container_id=env.running_scheduler().container_id,
        compose_project=compose_project,
        rollback_policy="FORBID_AFTER_DISPATCH",
        health_max_age_seconds=3600,
    )
    check_binding(root, scope)
    return ScopeEnvelope(scope_sha256=scope_hash(scope), scope=scope)


def prepare(root: Path, protocol_path: str, compose_project: str, env=None) -> dict[str, str]:
    env = env or SecureEnvironment(root, compose_project)
    envelope = build_scope(root, protocol_path, compose_project, env)
    directory = confined(root, SCOPE_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{envelope.scope_sha256}.scope.json"
    try:
        write_once(target, envelope.model_dump(mode="json"))
    except FileExistsError as error:
        raise ContractError("scope already prepared; a new scope needs new evidence") from error
    return {
        "status": "SCOPE_PREPARED_NOT_APPROVED",
        "scope_path": f"{SCOPE_DIR}/{target.name}",
        "scope_sha256": envelope.scope_sha256,
        "approval_text": approval_text(envelope.scope_sha256),
        "legacy_container_id": envelope.scope.legacy_container_id,
        "git_head": envelope.scope.git_head,
    }


def record_approval(root: Path, scope_path: str, text: str) -> dict[str, str]:
    envelope = load_scope(root, scope_path)
    expected = approval_text(envelope.scope_sha256)
    if text != expected:
        raise ContractError("approval text is not the exact verbatim text for this scope")
    directory = confined(root, APPROVAL_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{envelope.scope_sha256}.approval.json"
    approval = Approval(
        schema_version="r2d-execution-approval-v1",
        scope_sha256=envelope.scope_sha256,
        approval_text=text,
    )
    try:
        write_once(target, approval.model_dump(mode="json"))
    except FileExistsError as error:
        raise ContractError("approval already recorded for this scope") from error
    return {"status": "APPROVAL_RECORDED", "approval_path": f"{APPROVAL_DIR}/{target.name}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--protocol", required=True)
    prepare_parser.add_argument("--compose-project", default=default_compose_project())
    record_parser = commands.add_parser("record-approval")
    record_parser.add_argument("--scope", required=True)
    record_parser.add_argument("--text", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(PROJECT_ROOT, args.protocol, args.compose_project)
        else:
            result = record_approval(PROJECT_ROOT, args.scope, args.text)
    except Exception as error:  # 不回显嵌套命令输出或输入内容
        print(json.dumps({"status": "BLOCKED", "error_class": type(error).__name__,
                          "error": str(error)[:200]}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
