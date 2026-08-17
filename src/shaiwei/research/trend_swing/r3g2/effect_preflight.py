"""Run the reusable key-only R3G-2 pre-effect identity and coverage gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol
from shaiwei.research.trend_swing.r3g2.effect_inputs import RealInputAdapter
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json


def run(*, output: Path, temporary_root: Path) -> dict[str, object]:
    document = RealInputAdapter(EffectProtocol.load(), temporary_root).preflight()
    digest, reused = write_once_json(output, document)
    return {
        "pre_effect_preflight_sha256": digest,
        "reused": reused,
        "strategy_effect_attempt_count": 0,
        "real_score_or_outcome_read": False,
        "verdict": document["verdict"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--temporary-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
