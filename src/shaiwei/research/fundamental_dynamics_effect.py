"""Run the frozen F2-1 residual and historical effect stages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_dynamics_effect_contract import (
    FundamentalDynamicsEffectProtocol,
)
from shaiwei.research.fundamental_effect.contract import verify_inputs
from shaiwei.research.fundamental_effect.panel import build_residual_panels
from shaiwei.research.fundamental_effect.run import run_effect
from shaiwei.research.fundamental_effect.runtime import F2_RUNTIME


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--stage", choices=("residual", "effect", "all"), default="all")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else PROJECT_ROOT / args.protocol
    protocol = FundamentalDynamicsEffectProtocol.load(protocol_path)
    input_identity = verify_inputs(protocol)
    output: dict[str, object] = {}
    if args.stage in {"residual", "all"}:
        output["residual"] = build_residual_panels(protocol, input_identity, F2_RUNTIME)
    if args.stage in {"effect", "all"}:
        output["effect"] = run_effect(protocol, input_identity, F2_RUNTIME)
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
