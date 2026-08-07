"""Synthetic, no-data fixtures for R3 classification and ULP evidence."""

from __future__ import annotations

import json

from shaiwei.research.top30_provenance.classification import classify
from shaiwei.research.top30_provenance.topology import compare_rows, ulp_distance


def main() -> int:
    cases = {
        "ROOT_CAUSE_IDENTIFIED": {
            "unique_cause_proven": True,
            "competing_explanation_count": 0,
            "canonical_producer_identity_complete": True,
            "input_identity_pass": True,
        },
        "PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN": {
            "unique_cause_proven": False,
            "competing_explanation_count": 2,
            "canonical_producer_identity_complete": True,
            "input_identity_pass": True,
        },
        "PROVENANCE_GAP_CONFIRMED": {
            "unique_cause_proven": False,
            "competing_explanation_count": 0,
            "canonical_producer_identity_complete": False,
            "input_identity_pass": True,
        },
        "MIXED_UNRESOLVED": {
            "unique_cause_proven": False,
            "competing_explanation_count": 1,
            "canonical_producer_identity_complete": None,
            "input_identity_pass": True,
        },
    }
    observed = {name: classify(facts) for name, facts in cases.items()}
    if any(name != value for name, value in observed.items()):
        raise RuntimeError("Top30 provenance classification fixture failed")
    one = 1.0
    adjacent = float.fromhex("0x1.0000000000001p+0")
    if ulp_distance(one, adjacent) != 1:
        raise RuntimeError("Top30 provenance ULP fixture failed")
    expected = [{
        "date": "2020-01-01",
        "gross_return": one.hex(),
        "benchmark_return": 0.0.hex(),
        "recorded_cost": 0.0.hex(),
        "turnover": 0.0.hex(),
    }]
    actual = [{**expected[0], "gross_return": adjacent.hex()}]
    topology = compare_rows(expected, actual)
    if topology["mismatch_cell_count"] != 1 or topology["ulp"]["maximum"] != 1:
        raise RuntimeError("Top30 provenance topology fixture failed")
    print(json.dumps({"classification_fixture": "PASS", "topology_fixture": "PASS"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
