"""One-shot runner entry point for the versioned Top30 orchestration recovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.top30_diagnostic.recovery_contract import (
    RecoveryApproval,
    RecoveryProtocol,
    RecoveryReleaseScope,
    runtime_identity,
)
from shaiwei.research.top30_diagnostic.runner import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", choices=("original", "current"), required=True)
    parser.add_argument("--protocol", dest="protocol_path", type=Path, required=True)
    parser.add_argument("--release", dest="release_path", type=Path, required=True)
    parser.add_argument("--approval", dest="approval_path", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--m6-effect-root", type=Path, required=True)
    parser.add_argument("--failed-effect-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = run(
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
