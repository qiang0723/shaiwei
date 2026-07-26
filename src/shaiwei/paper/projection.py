"""Deterministic, fail-closed signal projections for independent paper accounts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json

from shaiwei.config import PaperTop20Portfolio


class PaperProjectionError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


@dataclass(frozen=True)
class ProjectedSignal:
    signal: dict[str, object]
    evidence: dict[str, object]


def project_top20_signal(
    signal: dict[str, object],
    *,
    source_signal_sha256: str,
    policy: PaperTop20Portfolio,
) -> ProjectedSignal:
    """Keep baseline ranks 1..20 and assign exactly five percent to each target."""
    if len(source_signal_sha256) != 64 or signal.get("signal_sha256") != source_signal_sha256:
        raise PaperProjectionError("Top20 source signal identity is invalid")
    if signal.get("topk") != policy.source_signal_topk:
        raise PaperProjectionError("Top20 source signal must freeze topk=30")
    if signal.get("rebalance_days") != policy.rebalance_days:
        raise PaperProjectionError("Top20 source signal rebalance period differs")
    orders = signal.get("orders")
    if not isinstance(orders, list) or len(orders) != policy.source_signal_topk:
        raise PaperProjectionError("Top20 source signal must contain exactly 30 orders")

    normalized: list[dict[str, object]] = []
    instruments: set[str] = set()
    ranks: set[int] = set()
    source_weight_sum = Decimal("0")
    expected_source_weight = Decimal(1) / Decimal(policy.source_signal_topk)
    for value in orders:
        if not isinstance(value, dict):
            raise PaperProjectionError("Top20 source order must be an object")
        try:
            instrument = str(value["instrument"])
            rank = int(value["rank"])
            weight = Decimal(str(value["target_weight"]))
        except (KeyError, TypeError, ValueError) as error:
            raise PaperProjectionError("Top20 source order is incomplete") from error
        upper = instrument.upper()
        if upper.startswith("BJ") or upper.endswith(".BJ"):
            raise PaperProjectionError("Top20 source signal contains forbidden BSE instrument")
        if instrument in instruments or rank in ranks:
            raise PaperProjectionError("Top20 source signal contains duplicate instrument or rank")
        if abs(weight - expected_source_weight) > Decimal("1e-12"):
            raise PaperProjectionError("Top20 source signal is not the frozen equal-weight Top30")
        instruments.add(instrument)
        ranks.add(rank)
        source_weight_sum += weight
        normalized.append(dict(value))
    if ranks != set(range(1, policy.source_signal_topk + 1)):
        raise PaperProjectionError("Top20 source ranks must be exactly 1 through 30")
    if abs(source_weight_sum - Decimal(1)) > Decimal("1e-12"):
        raise PaperProjectionError("Top20 source signal weights do not sum to one")

    selected: list[dict[str, object]] = []
    for order in sorted(normalized, key=lambda value: int(value["rank"]))[: policy.target_topk]:
        selected.append({**order, "target_weight": policy.target_weight})
    if [int(order["rank"]) for order in selected] != list(range(1, policy.target_topk + 1)):
        raise PaperProjectionError("Top20 projection did not preserve ranks 1 through 20")

    unsigned_evidence: dict[str, object] = {
        "schema_version": "paper-signal-projection-v1",
        "projection_policy": policy.target_projection,
        "source_account_id": policy.source_account_id,
        "source_signal_sha256": source_signal_sha256,
        "source_topk": policy.source_signal_topk,
        "target_topk": policy.target_topk,
        "target_weight": policy.target_weight,
        "orders": selected,
    }
    projection_sha256 = hashlib.sha256(_canonical(unsigned_evidence)).hexdigest()
    evidence = {**unsigned_evidence, "projection_sha256": projection_sha256}
    projected = {
        **signal,
        "topk": policy.target_topk,
        "orders": selected,
        "source_signal_sha256": source_signal_sha256,
        "signal_projection": evidence,
    }
    return ProjectedSignal(signal=projected, evidence=evidence)
