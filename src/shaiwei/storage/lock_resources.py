"""Stable logical identities and ordering for runtime interprocess locks."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from shaiwei.config import PROJECT_ROOT


DAILY_CYCLE = "runtime:daily-cycle"
SHADOW_CYCLE = "runtime:shadow-cycle"
PAPER_CYCLE = "runtime:paper-cycle"

_EXACT_RANKS = {
    DAILY_CYCLE: 10,
    SHADOW_CYCLE: 10,
    PAPER_CYCLE: 10,
}
_TIMELINE_PATTERN = re.compile(r"^runtime:scheduler-timeline:(\d{8})$")
_LEDGER_PATTERN = re.compile(r"^ledger:([A-Za-z0-9_.-]+\.csv)$")
_LOCAL_PATTERN = re.compile(r"^local:(daily|shadow|paper|ledger):([0-9a-f]{64})$")
_TIMELINE_FILE = re.compile(r"^timeline_(\d{8})\.jsonl$")


class LockResourceError(ValueError):
    """The caller supplied an unregistered or unsafe lock identity."""


@dataclass(frozen=True)
class LockResourceSpec:
    resource_id: str
    rank: int
    local_only: bool = False


def resource_spec(resource_id: str) -> LockResourceSpec:
    """Validate one complete logical identity and return its lock-order rank."""
    if resource_id in _EXACT_RANKS:
        return LockResourceSpec(resource_id, _EXACT_RANKS[resource_id])
    if _TIMELINE_PATTERN.fullmatch(resource_id):
        return LockResourceSpec(resource_id, 20)
    if _LEDGER_PATTERN.fullmatch(resource_id):
        return LockResourceSpec(resource_id, 30)
    local = _LOCAL_PATTERN.fullmatch(resource_id)
    if local:
        rank = 30 if local.group(1) == "ledger" else 10
        return LockResourceSpec(resource_id, rank, local_only=True)
    raise LockResourceError(f"unregistered lock resource: {resource_id!r}")


def timeline_resource(path: Path) -> str:
    match = _TIMELINE_FILE.fullmatch(path.name)
    if match is None:
        raise LockResourceError("timeline lock path has an invalid filename")
    return f"runtime:scheduler-timeline:{match.group(1)}"


def ledger_resource(path: Path) -> str:
    """Use a portable basename in production and an isolated hash in tests."""
    resolved = path.resolve(strict=False)
    ledger_root = (PROJECT_ROOT / "ledger").resolve(strict=False)
    if resolved.parent == ledger_root:
        return f"ledger:{resolved.name}"
    return _local_resource("ledger", resolved)


def cycle_resource(name: str, override_path: Path | None = None) -> str:
    exact = {
        "daily": DAILY_CYCLE,
        "shadow": SHADOW_CYCLE,
        "paper": PAPER_CYCLE,
    }
    try:
        resource_id = exact[name]
    except KeyError as error:
        raise LockResourceError(f"unknown cycle lock: {name!r}") from error
    return resource_id if override_path is None else _local_resource(name, override_path)


def _local_resource(kind: str, path: Path) -> str:
    digest = hashlib.sha256(str(path.resolve(strict=False)).encode("utf-8")).hexdigest()
    return f"local:{kind}:{digest}"
