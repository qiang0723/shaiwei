"""Stable provenance identifiers shared by reports, manifests, and ledgers."""

import hashlib
from pathlib import Path
import subprocess


CONTROLLED_ROOTS = ("src/", "config/", "templates/", "tests/")
CONTROLLED_FILES = {
    ".env.example",
    "Makefile",
    "pyproject.toml",
    "requirements.lock",
}


def _is_controlled_input(name: str) -> bool:
    return name in CONTROLLED_FILES or name.startswith(CONTROLLED_ROOTS)


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def code_snapshot_sha256() -> str:
    """Hash executable, configuration, dependency, template, and test inputs.

    HEAD and documentation/status/evidence files are intentionally absent:
    committing or backfilling an unchanged run must not invalidate its reports.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True
    ).stdout.split(b"\0")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    names = sorted(
        name.decode("utf-8")
        for name in {*tracked, *untracked}
        if name and _is_controlled_input(name.decode("utf-8"))
    )
    payload = hashlib.sha256()
    for name in names:
        path = Path(name)
        if not path.is_file():
            continue
        payload.update(name.encode("utf-8"))
        payload.update(b"\0")
        payload.update(hashlib.sha256(path.read_bytes()).digest())
    return payload.hexdigest()
