"""已关闭研究线冻结输入的身份核验（ADR 0018）：活文件未漂移按现状通过，漂移时按冻结提交的历史版本核验。

只服务已冻结协议的离线复核，不得用来签发新的执行授权；新 release / 新协议仍须使用当前文件哈希。
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path, PurePosixPath
from typing import Callable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT

AUTHORITY_PATH = PROJECT_ROOT / "config" / "closed_lane_frozen_input_authority_v1.yaml"
GitRunner = Callable[[list[str]], subprocess.CompletedProcess]
Identity = Literal["LIVE", "HISTORICAL"]


class FrozenInputIdentityError(RuntimeError):
    """冻结输入既不等于活文件，也无法由冻结提交的历史版本证明。"""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorityEntry(_Frozen):
    protocol_path: str
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    freeze_commit: str = Field(pattern=r"^[0-9a-f]{40}$")


class Authority(_Frozen):
    schema_version: Literal["closed-lane-frozen-input-authority-v1"]
    authority_id: Literal["adr-0018-v1"]
    document: str
    entries: tuple[AuthorityEntry, ...] = Field(min_length=1)

    def entry(self, protocol_path: str) -> AuthorityEntry:
        matches = [entry for entry in self.entries if entry.protocol_path == protocol_path]
        if len(matches) != 1:
            raise FrozenInputIdentityError(f"no unique frozen-input authority for {protocol_path}")
        return matches[0]


def load_authority(path: Path = AUTHORITY_PATH) -> Authority:
    return Authority.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def git_runner_for(root: Path) -> GitRunner:
    def run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)

    return run


def _confined(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise FrozenInputIdentityError(f"frozen input path is not a confined relative path: {relative}")
    resolved = (root / relative).resolve()
    if root.resolve() not in resolved.parents:
        raise FrozenInputIdentityError(f"frozen input path escapes the project: {relative}")
    return resolved


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _historical_blob(git: GitRunner, commit: str, relative: str) -> bytes:
    try:
        ancestor = git(["merge-base", "--is-ancestor", commit, "HEAD"])
        if ancestor.returncode != 0:
            raise FrozenInputIdentityError(f"freeze commit {commit[:12]} is not an ancestor of HEAD")
        blob = git(["show", f"{commit}:{relative}"])
    except (OSError, subprocess.SubprocessError) as error:
        raise FrozenInputIdentityError(f"git is unavailable: {type(error).__name__}") from error
    if blob.returncode != 0:
        raise FrozenInputIdentityError(f"{relative} is absent at freeze commit {commit[:12]}")
    return blob.stdout


def verify_frozen_input(
    relative: str,
    expected_sha256: str,
    *,
    protocol_path: str,
    root: Path = PROJECT_ROOT,
    git: GitRunner | None = None,
    authority: Authority | None = None,
) -> Identity:
    """返回 LIVE 或 HISTORICAL；任何无法证明的情形抛 FrozenInputIdentityError（ADR 0018 §4.2）。"""
    path = _confined(root, relative)
    if path.is_file() and not path.is_symlink() and _sha256(path.read_bytes()) == expected_sha256:
        return "LIVE"
    entry = (authority or load_authority()).entry(protocol_path)
    protocol = _confined(root, entry.protocol_path)
    if not protocol.is_file() or _sha256(protocol.read_bytes()) != entry.protocol_sha256:
        raise FrozenInputIdentityError(f"frozen protocol identity differs: {protocol_path}")
    blob = _historical_blob(git or git_runner_for(root), entry.freeze_commit, relative)
    if _sha256(blob) != expected_sha256:
        raise FrozenInputIdentityError(f"{relative} at freeze commit does not match the frozen hash")
    return "HISTORICAL"
