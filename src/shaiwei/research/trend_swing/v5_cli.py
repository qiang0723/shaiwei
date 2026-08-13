"""Offline TS-v5 candidate contract and prompt preflight commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.v5_contract import V5Bundle, V5ContractError, canonical_json
from shaiwei.research.trend_swing.v5_models import MechanismCandidate, candidate_schema
from shaiwei.research.trend_swing.v5_prompt import plan_attempt, preflight, validate_response


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("TS-v5 candidate input must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema")
    commands.add_parser("preflight")
    validator = commands.add_parser("validate")
    validator.add_argument("--ordinal", type=int, required=True)
    validator.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            result: object = candidate_schema()
        elif args.command == "preflight":
            result = preflight()
        else:
            bundle = V5Bundle.load()
            plan = plan_attempt(bundle, args.ordinal)
            candidate: MechanismCandidate = validate_response(plan, _load_json(args.input))
            result = {
                "attempt_id": plan.attempt_id,
                "candidate_fingerprint": candidate.fingerprint(),
                "semantic_signature": candidate.semantic_signature(),
                "validation_gate": "PASS",
                "provider_calls": 0,
            }
    except (OSError, json.JSONDecodeError, ValueError, V5ContractError) as exc:
        print(canonical_json({"gate": "FAIL", "error_class": type(exc).__name__}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
