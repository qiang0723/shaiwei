"""Stable provenance identifiers shared by reports, manifests, and ledgers."""

import hashlib
from pathlib import Path
import subprocess


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def code_snapshot_sha256() -> str:
    """Hash HEAD plus source/config changes, excluding append-only evidence."""
    head = git_head()
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--binary",
            "HEAD",
            "--",
            ".",
            ":(exclude)ledger/*.csv",
            ":(exclude)signals/**",
        ],
        capture_output=True,
        check=True,
    ).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    untracked_payload = bytearray()
    for name in sorted(untracked):
        if name.startswith(("ledger/", "signals/")):
            continue
        path = Path(name)
        if path.is_file():
            untracked_payload.extend(name.encode())
            untracked_payload.extend(b"\0")
            untracked_payload.extend(hashlib.sha256(path.read_bytes()).digest())
    return hashlib.sha256(head.encode() + b"\0" + diff + b"\0" + untracked_payload).hexdigest()
