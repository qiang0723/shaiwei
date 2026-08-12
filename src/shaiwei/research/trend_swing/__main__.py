"""Execute the one permitted TS-1A profile and its independent audit."""

import json

from shaiwei.research.trend_swing.audit import audit_once
from shaiwei.research.trend_swing.run import run_once


def main() -> int:
    report = run_once()
    audit = audit_once()
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "blocking_verdicts": report["blocking_verdicts"],
                "audit": audit["verdict"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
