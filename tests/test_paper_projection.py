from copy import deepcopy

import pytest

from shaiwei.config import load_paper_top20_protocol
from shaiwei.paper.projection import PaperProjectionError, project_top20_signal


def _signal() -> dict[str, object]:
    orders = [
        {
            "rank": rank,
            "instrument": f"SH{600000 + rank:06d}",
            "score": float(100 - rank),
            "target_weight": 1 / 30,
        }
        for rank in range(1, 31)
    ]
    return {
        "signal_sha256": "a" * 64,
        "signal_date": "2026-07-24",
        "topk": 30,
        "rebalance_days": 10,
        "rebalance_due": True,
        "orders": orders,
    }


def _project(signal: dict[str, object] | None = None):
    return project_top20_signal(
        signal or _signal(),
        source_signal_sha256="a" * 64,
        policy=load_paper_top20_protocol().paper_portfolio,
    )


def test_top20_projection_is_deterministic_rank_preserving_and_equal_weight():
    source = _signal()
    reversed_source = {**source, "orders": list(reversed(source["orders"]))}
    first = _project(source)
    second = _project(reversed_source)
    assert first == second
    orders = first.signal["orders"]
    assert len(orders) == 20
    assert [order["rank"] for order in orders] == list(range(1, 21))
    assert [order["instrument"] for order in orders] == [
        f"SH{600000 + rank:06d}" for rank in range(1, 21)
    ]
    assert {order["target_weight"] for order in orders} == {0.05}
    assert first.evidence["source_signal_sha256"] == "a" * 64
    assert len(first.evidence["projection_sha256"]) == 64
    assert source["orders"][0]["target_weight"] == 1 / 30


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda value: value["orders"].pop(), "exactly 30"),
        (lambda value: value["orders"].__setitem__(1, dict(value["orders"][0])), "duplicate"),
        (lambda value: value["orders"][0].__setitem__("rank", 31), "exactly 1 through 30"),
        (lambda value: value["orders"][0].__setitem__("instrument", "BJ920001"), "BSE"),
        (lambda value: value["orders"][0].__setitem__("target_weight", 0.1), "equal-weight"),
    ],
)
def test_top20_projection_fails_closed_on_source_contract_violation(mutator, message):
    signal = deepcopy(_signal())
    mutator(signal)
    with pytest.raises(PaperProjectionError, match=message):
        _project(signal)


def test_top20_projection_rejects_wrong_source_hash():
    with pytest.raises(PaperProjectionError, match="identity"):
        project_top20_signal(
            _signal(),
            source_signal_sha256="b" * 64,
            policy=load_paper_top20_protocol().paper_portfolio,
        )
