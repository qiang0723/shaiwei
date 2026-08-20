"""Independent M6-5B-R1 auditor using the repaired explicit CLI mapping."""

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
from .release_audit import audit_loaded


def audit(
    *, release_path: Path, approval_path: Path, effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    protocol = EntrypointRecoveryProtocol.load()
    release = EntrypointRecoveryScope.load(release_path, protocol)
    approval = EntrypointRecoveryApproval.load(approval_path, release)
    return audit_loaded(
        release=release, approval=approval, effect_root=effect_root, audit_root=audit_root,
    )


def main(argv: list[str] | None = None, *, auditor: Any = audit) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = auditor(
        release_path=args.release,
        approval_path=args.approval,
        effect_root=args.effect_root,
        audit_root=args.audit_root,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
