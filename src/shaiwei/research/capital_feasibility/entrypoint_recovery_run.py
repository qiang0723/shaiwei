"""One-shot M6-5B-R1 runner using the repaired explicit CLI mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .entrypoint_recovery_contract import (
    EntrypointRecoveryApproval,
    EntrypointRecoveryProtocol,
    EntrypointRecoveryScope,
)
from .release_run import execute_loaded


def run(
    *, release_path: Path, approval_path: Path, r2_root: Path, r7_audit: Path,
    raw_manifest: Path, project_root: Path, output_root: Path,
) -> dict[str, Any]:
    protocol = EntrypointRecoveryProtocol.load()
    release = EntrypointRecoveryScope.load(release_path, protocol)
    approval = EntrypointRecoveryApproval.load(approval_path, release)
    return execute_loaded(
        release=release, approval=approval, r2_root=r2_root, r7_audit=r7_audit,
        raw_manifest=raw_manifest, project_root=project_root, output_root=output_root,
    )


def main(argv: list[str] | None = None, *, executor: Any = run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--r2-root", type=Path, required=True)
    parser.add_argument("--r7-audit", type=Path, required=True)
    parser.add_argument("--raw-manifest", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = executor(
        release_path=args.release,
        approval_path=args.approval,
        r2_root=args.r2_root,
        r7_audit=args.r7_audit,
        raw_manifest=args.raw_manifest,
        project_root=args.project_root,
        output_root=args.output_root,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
