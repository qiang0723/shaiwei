"""Thread, process, and container lock adapter over stable logical resources."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import fcntl
import hashlib
import os
from pathlib import Path
import re
import threading
from typing import Iterator

from shaiwei.config import PROJECT_ROOT
from shaiwei.storage.lock_resources import LockResourceSpec, resource_spec


LOCK_AUTHORITY_ENV = "SHAIWEI_LOCK_AUTHORITY"
LOCK_ROOT_ENV = "SHAIWEI_LOCK_ROOT"
DOCKER_AUTHORITY = "docker-named-volume-v1"
DOCKER_LOCK_ROOT = Path("/run/shaiwei-locks")
LOCAL_LOCK_ROOT = PROJECT_ROOT / ".runtime-locks"


class LockMode(str, Enum):
    EXCLUSIVE = "exclusive"
    SHARED = "shared"


class InterprocessLockError(RuntimeError):
    pass


class LockBusy(InterprocessLockError):
    pass


class LockConfigurationError(InterprocessLockError):
    pass


class LockOrderError(InterprocessLockError):
    pass


@dataclass
class _MutexEntry:
    mutex: threading.Lock = field(default_factory=threading.Lock)
    users: int = 0


_REGISTRY_GUARD = threading.Lock()
_PROCESS_MUTEXES: dict[str, _MutexEntry] = {}
_HELD = threading.local()


def _held_stack() -> list[LockResourceSpec]:
    stack = getattr(_HELD, "stack", None)
    if stack is None:
        stack = []
        _HELD.stack = stack
    return stack


def _validate_order(spec: LockResourceSpec) -> None:
    stack = _held_stack()
    if any(held.resource_id == spec.resource_id for held in stack):
        raise LockOrderError(f"reentrant lock acquisition is forbidden: {spec.resource_id}")
    if stack and spec.rank <= stack[-1].rank:
        raise LockOrderError(
            f"lock order violation: {stack[-1].resource_id} -> {spec.resource_id}"
        )


def _resolve_root(explicit: Path | None) -> tuple[Path, bool]:
    authority = os.getenv(LOCK_AUTHORITY_ENV, "").strip()
    configured = os.getenv(LOCK_ROOT_ENV, "").strip()
    release_manifest = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
    if authority:
        if authority != DOCKER_AUTHORITY:
            raise LockConfigurationError(f"unknown lock authority: {authority!r}")
        if explicit is not None or configured != str(DOCKER_LOCK_ROOT):
            raise LockConfigurationError("Docker lock authority has an invalid root")
        root = DOCKER_LOCK_ROOT
        if not root.is_dir() or not os.path.ismount(root):
            raise LockConfigurationError("Docker lock root is missing or is not a mount")
        return root, True
    if release_manifest:
        raise LockConfigurationError("released runtime lacks Docker lock authority")
    root = explicit or (Path(configured) if configured else LOCAL_LOCK_ROOT)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise LockConfigurationError("local lock root cannot be created") from error
    return root.resolve(strict=True), False


def _lock_path(root: Path, resource_id: str) -> Path:
    prefix = re.sub(r"[^a-z0-9]+", "-", resource_id.lower()).strip("-")[:32]
    digest = hashlib.sha256(resource_id.encode("utf-8")).hexdigest()
    return root / f"{prefix}-{digest}.lock"


def _register_mutex(key: str) -> _MutexEntry:
    with _REGISTRY_GUARD:
        entry = _PROCESS_MUTEXES.get(key)
        if entry is None:
            entry = _MutexEntry()
            _PROCESS_MUTEXES[key] = entry
        entry.users += 1
        return entry


def _release_mutex(key: str, entry: _MutexEntry, acquired: bool) -> None:
    if acquired:
        entry.mutex.release()
    with _REGISTRY_GUARD:
        entry.users -= 1
        if entry.users == 0:
            _PROCESS_MUTEXES.pop(key, None)


def _acquire_flock(handle, mode: LockMode, blocking: bool) -> None:
    handle.seek(0)
    initially_empty = not handle.read(1)
    requested = fcntl.LOCK_EX if mode is LockMode.EXCLUSIVE else fcntl.LOCK_SH
    operation = fcntl.LOCK_EX if mode is LockMode.SHARED and initially_empty else requested
    if not blocking:
        operation |= fcntl.LOCK_NB
    try:
        fcntl.flock(handle.fileno(), operation)
    except BlockingIOError as error:
        raise LockBusy("logical lock is already held") from error


def _validate_or_initialize_identity(handle, resource_id: str, mode: LockMode) -> None:
    handle.seek(0)
    identity = handle.read().strip()
    if not identity:
        handle.seek(0)
        handle.write(resource_id + "\n")
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
        identity = resource_id
    if identity != resource_id:
        raise LockConfigurationError("lock filename identity collision")
    if mode is LockMode.SHARED:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)


@contextmanager
def logical_lock(
    resource_id: str,
    *,
    mode: LockMode = LockMode.EXCLUSIVE,
    blocking: bool = True,
    lock_root: Path | None = None,
) -> Iterator[None]:
    """Acquire one registered logical resource and release it on every exit path."""
    if not isinstance(mode, LockMode):
        raise LockConfigurationError("unknown lock mode")
    spec = resource_spec(resource_id)
    _validate_order(spec)
    root, production = _resolve_root(lock_root)
    if production and spec.local_only:
        raise LockConfigurationError("local-only lock resource reached production")
    path = _lock_path(root, resource_id)
    key = f"{root}:{resource_id}"
    entry = _register_mutex(key)
    acquired = entry.mutex.acquire(blocking=blocking)
    if not acquired:
        _release_mutex(key, entry, False)
        raise LockBusy("logical lock is already held in this process")
    try:
        try:
            handle = path.open("a+", encoding="utf-8")
        except OSError as error:
            raise LockConfigurationError("lock root is not writable") from error
        with handle:
            _acquire_flock(handle, mode, blocking)
            try:
                _validate_or_initialize_identity(handle, resource_id, mode)
                stack = _held_stack()
                stack.append(spec)
                try:
                    yield
                finally:
                    popped = stack.pop()
                    if popped != spec:
                        raise LockOrderError("logical lock stack is corrupted")
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        _release_mutex(key, entry, True)


def active_process_lock_count() -> int:
    """Expose only registry cardinality for invariant tests."""
    with _REGISTRY_GUARD:
        return len(_PROCESS_MUTEXES)
