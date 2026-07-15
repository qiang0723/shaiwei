"""Stable provenance identifiers shared by reports, manifests, and ledgers."""

import hashlib
from pathlib import Path
import subprocess


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def code_snapshot_sha256() -> str:
    """Hash controlled working-tree content, excluding append-only evidence.

    HEAD itself is intentionally absent: an evidence-only ledger commit must
    not invalidate reports produced by identical code and configuration.
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
        if name
        and not name.startswith((b"ledger/", b"signals/"))
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
