"""Process-local serialization for scheduler timeline append paths."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Iterator


@dataclass
class _PathMutexEntry:
    mutex: threading.Lock = field(default_factory=threading.Lock)
    users: int = 0


_REGISTRY_MUTEX = threading.Lock()
_PATH_MUTEXES: dict[str, _PathMutexEntry] = {}


def _canonical_key(path: Path) -> str:
    return str(path.resolve(strict=False))


@contextmanager
def timeline_path_mutex(path: Path) -> Iterator[None]:
    """Serialize threads targeting one canonical path and release idle entries."""
    key = _canonical_key(path)
    with _REGISTRY_MUTEX:
        entry = _PATH_MUTEXES.get(key)
        if entry is None:
            entry = _PathMutexEntry()
            _PATH_MUTEXES[key] = entry
        entry.users += 1

    acquired = False
    try:
        entry.mutex.acquire()
        acquired = True
        yield
    finally:
        if acquired:
            entry.mutex.release()
        with _REGISTRY_MUTEX:
            entry.users -= 1
            if entry.users == 0:
                _PATH_MUTEXES.pop(key, None)


def _active_path_mutex_count() -> int:
    """Return the active/waiting registry size for invariant tests."""
    with _REGISTRY_MUTEX:
        return len(_PATH_MUTEXES)
