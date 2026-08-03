"""Command-line entry point for the frozen F1-1 research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_effect.contract import (
    FundamentalEffectProtocol,
    verify_inputs,
)
from shaiwei.research.fundamental_effect.panel import build_residual_panels
from shaiwei.research.fundamental_effect.run import run_effect


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--stage", choices=("residual", "effect", "all"), default="all")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else PROJECT_ROOT / args.protocol
    protocol = FundamentalEffectProtocol.load(protocol_path)
    input_identity = verify_inputs(protocol)
    output: dict[str, object] = {}
    if args.stage in {"residual", "all"}:
        output["residual"] = build_residual_panels(protocol, input_identity)
    if args.stage in {"effect", "all"}:
        output["effect"] = run_effect(protocol, input_identity)
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
