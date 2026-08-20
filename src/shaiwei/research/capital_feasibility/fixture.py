"""No-market-data adversarial fixture for M6-5A."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path

from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.real_contract import write_once_document

from .contract import Policy, load_protocol
from .execution import Account, Target, rebalance
from .verdict import evaluate


def _targets(price: str) -> list[Target]:
    return [
        Target(f"{600000 + index:06d}.SH", float(30 - index), Decimal(price))
        for index in range(30)
    ]


def build_fixture() -> dict:
    load_protocol()
    effect = {
        "positive_window_count": 5, "combined_1_5x_net_excess": 0.10,
        "executable_to_ideal_pooled_nav_ratio": 0.99,
    }
    first_record = rebalance(Account(Policy().initial_cash, {}), _targets("10"))
    replay_record = rebalance(Account(Policy().initial_cash, {}), _targets("10"))
    if canonical_sha256(first_record) != canonical_sha256(replay_record):
        raise RuntimeError("M6-5A replay differs")
    feasible = evaluate([first_record] * 6, effect)
    expensive = rebalance(Account(Policy().initial_cash, {}), _targets("1000"))
    infeasible = evaluate([expensive] * 6, effect)
    if feasible["decision"] != "CAPITAL_FEASIBLE_RESEARCH_ONLY":
        raise RuntimeError("M6-5A feasible fixture failed")
    if infeasible["decision"] != "CAPITAL_INFEASIBLE":
        raise RuntimeError("M6-5A minimum-lot fixture did not fail")
    return {
        "schema_version": "m6-head30-500k-feasibility-fixture-v1", "status": "PASS",
        "deterministic_replay": "PASS", "feasible_path": "PASS",
        "minimum_lot_fail_closed": "PASS", "real_market_data_read": False,
        "real_effect_read": False, "qlib_read": False, "model_fit_count": 0,
        "prediction_generation_count": 0, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    document = build_fixture()
    digest, reused = write_once_document(parser.parse_args().output, document)
    print(json.dumps({**document, "sha256": digest, "reused": reused}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
