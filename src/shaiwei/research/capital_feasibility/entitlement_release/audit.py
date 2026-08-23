"""Independent artifact-only audit for the ordinal-two entitlement release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..delisting_release_audit import audit_loaded
from .contract import Approval, ReleaseProtocol, ReleaseScope


def audit(**paths: Path) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    release = ReleaseScope.load(paths.pop("release_path"), protocol)
    approval = Approval.load(paths.pop("approval_path"), release)
    return audit_loaded(
        release=release,
        approval=approval,
        family_attempts_before_run=1,
        total_family_attempts=2,
        **paths,
    )


def main(argv: list[str] | None = None, *, auditor: Any = audit) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "release",
        "approval",
        "effect-root",
        "ledger",
        "claim-receipt",
        "audit-root",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    values = vars(parser.parse_args(argv))
    result = auditor(
        release_path=values["release"],
        approval_path=values["approval"],
        effect_root=values["effect_root"],
        ledger_path=values["ledger"],
        receipt_path=values["claim_receipt"],
        audit_root=values["audit_root"],
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
