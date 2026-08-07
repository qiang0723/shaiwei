"""Independent audit entry point for the versioned Top30 orchestration recovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.top30_diagnostic.audit import audit
from shaiwei.research.top30_diagnostic.recovery_contract import (
    RecoveryApproval,
    RecoveryProtocol,
    RecoveryReleaseScope,
    runtime_identity,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", dest="protocol_path", type=Path, required=True)
    parser.add_argument("--release", dest="release_path", type=Path, required=True)
    parser.add_argument("--approval", dest="approval_path", type=Path, required=True)
    parser.add_argument("--canonical-report", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        **vars(args),
        protocol_loader=RecoveryProtocol.load,
        release_loader=RecoveryReleaseScope.load,
        approval_loader=RecoveryApproval.load,
        runtime_verifier=runtime_identity,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
