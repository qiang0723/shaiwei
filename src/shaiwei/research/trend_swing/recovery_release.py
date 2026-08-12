"""Build the immutable TS-1A-R3 release before exact user authorization."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import INGEST
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.contract import TrendSwingError, sha256_file
from shaiwei.research.trend_swing.recovery_contract import (
    RELEASE_SCOPE_PATH,
    RecoveryAddendum,
    RecoveryProtocol,
    RecoveryR2,
    RecoveryR2Addendum,
    release_scope_payload,
)
from shaiwei.research.trend_swing.recovery_r3_contract import RecoveryR3


def _origin_main() -> str:
    return subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip().lower()


def build_release_document(ledger_path: Path = INGEST) -> dict[str, Any]:
    protocol = RecoveryProtocol.load()
    addendum = RecoveryAddendum.load(protocol)
    recovery_r2 = RecoveryR2.load(protocol, addendum)
    recovery_r2_addendum = RecoveryR2Addendum.load(recovery_r2)
    recovery_r3 = RecoveryR3.load(recovery_r2, recovery_r2_addendum)
    head = git_head()
    if head != _origin_main():
        raise TrendSwingError("TS recovery implementation HEAD is not pushed origin/main")
    return release_scope_payload(
        protocol,
        addendum,
        recovery_r2,
        recovery_r2_addendum,
        recovery_r3,
        implementation_snapshot_sha256=code_snapshot_sha256(),
        implementation_git_head=head,
        ingest_ledger_sha256=sha256_file(ledger_path),
    )


def write_release_once(path: Path = RELEASE_SCOPE_PATH) -> dict[str, Any]:
    document = build_release_document()
    payload = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise TrendSwingError("TS recovery R3 release already exists") from error
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RELEASE_SCOPE_PATH)
    args = parser.parse_args(argv)
    document = write_release_once(args.output)
    print(document["release_scope_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
