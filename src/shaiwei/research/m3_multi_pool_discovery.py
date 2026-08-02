"""Real discovery-period evaluator and immutable feedback projection for M3-2."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.alphagen_expression import ExpressionSafetyError, audit_expression, parse_safe_expression
from shaiwei.research.llm_factor import AttemptPlan, D1ControlError, DiscoveryEvidence
from shaiwei.research.m3_multi_pool_contract import M3Protocol, POOL_IDS
from shaiwei.research.m3_multi_pool_data import M3DiscoveryInput, build_m3_discovery_input
from shaiwei.research.m3_multi_pool_evaluation import evaluate_cross_pool_candidate
from shaiwei.research.m3_multi_pool_release import M3ExecutionRelease


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError("immutable M3-2 discovery artifact differs")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def plan_m3_attempt(protocol: M3Protocol, global_ordinal: int) -> AttemptPlan:
    topics = tuple(protocol.prompt_bundle.document["topic_order"])
    total = len(topics) * protocol.attempts_per_topic
    if not 1 <= global_ordinal <= total:
        raise D1ControlError(f"M3-2 global ordinal must be within 1..{total}")
    topic_index, zero_based = divmod(global_ordinal - 1, protocol.attempts_per_topic)
    topic_ordinal = zero_based + 1
    identity = f"{protocol.protocol_id}:{protocol.sha256}:{global_ordinal}"
    return AttemptPlan(
        attempt_id=hashlib.sha256(identity.encode()).hexdigest()[:16],
        global_ordinal=global_ordinal,
        topic=str(topics[topic_index]),
        topic_ordinal=topic_ordinal,
        evolution_mode=(
            "independent" if topic_ordinal <= protocol.independent_attempts else "mutation"
        ),
    )


def _pool_document(value: Any) -> dict[str, Any]:
    document = asdict(value)
    document["failures"] = list(document["failures"])
    return document


@dataclass
class M3DiscoveryEvaluator:
    protocol: M3Protocol
    release: M3ExecutionRelease
    artifact_root: Path
    prepared: M3DiscoveryInput | None = None

    def __post_init__(self) -> None:
        self.prepared = self.prepared or build_m3_discovery_input(self.protocol)
        self.release.verify_input(self.prepared.identity)
        self.data_snapshot_sha256 = self.prepared.identity.snapshot_sha256

    def __call__(self, plan: AttemptPlan, expression: str) -> DiscoveryEvidence:
        if self.prepared is None:
            raise D1ControlError("M3-2 discovery input is absent")
        evaluated = parse_safe_expression(expression).evaluate(self.prepared.stock_data)
        values = evaluated.detach().cpu().numpy()
        expected_shape = (
            len(self.prepared.discovery_dates),
            len(self.prepared.instruments),
        )
        if values.shape != expected_shape:
            raise D1ControlError("M3-2 factor panel shape differs")
        factor = pd.DataFrame(
            {
                "trade_date": np.repeat(
                    self.prepared.discovery_dates, len(self.prepared.instruments)
                ),
                "instrument": list(self.prepared.instruments)
                * len(self.prepared.discovery_dates),
                "factor": values.reshape(-1),
            }
        ).reset_index(drop=True)
        base = factor.merge(
            self.prepared.labels,
            on=["trade_date", "instrument"],
            how="inner",
            validate="one_to_one",
        ).merge(
            self.prepared.exposures,
            on=["trade_date", "instrument"],
            how="inner",
            validate="one_to_one",
        )
        members = self.prepared.members.copy()
        members["trade_date"] = pd.to_datetime(members["trade_date"], format="%Y%m%d")
        instrument_by_code = {
            f"{instrument[2:]}.{instrument[:2]}": instrument
            for instrument in self.prepared.instruments
        }
        members["instrument"] = members["ts_code"].map(instrument_by_code)
        if members["instrument"].isna().any():
            raise D1ControlError("M3-2 member/instrument mapping differs")
        frames = {
            pool_id: members.loc[
                members["universe_id"].eq(pool_id), ["trade_date", "instrument"]
            ].merge(
                base,
                on=["trade_date", "instrument"],
                how="left",
                validate="one_to_one",
            )
            for pool_id in POOL_IDS.values()
        }
        evidence = evaluate_cross_pool_candidate(
            expression,
            frames,
            self.protocol,
            global_ordinal=plan.global_ordinal,
        )
        structurally_evaluated = (
            evidence.direction is not None
            and len(evidence.directed_rank_ic) == len(POOL_IDS)
            and all(pool.structural_pass for pool in evidence.pool_evidence.values())
        )
        artifact = {
            "schema_version": "m3-multi-pool-discovery-evidence-v1",
            "attempt_id": plan.attempt_id,
            "global_ordinal": plan.global_ordinal,
            "topic": plan.topic,
            "canonical_expression": evidence.normalized_expression,
            "expression_sha256": evidence.candidate_id,
            "data_snapshot_sha256": self.data_snapshot_sha256,
            "direction_anchor_universe": POOL_IDS["all"],
            "direction": evidence.direction,
            "pool_evidence": {
                pool: _pool_document(value)
                for pool, value in sorted(evidence.pool_evidence.items())
            },
            "directed_rank_ic": dict(sorted(evidence.directed_rank_ic.items())),
            "cross_pool_score": evidence.cross_pool_score,
            "secondary_score": evidence.secondary_score,
            "minimum_coverage": evidence.minimum_coverage,
            "eligible": evidence.eligible,
            "failures": list(evidence.failures),
            "sealed_validation_read": False,
            "stress_periods_read": False,
            "g1_run": False,
            "model_or_portfolio_run": False,
        }
        relative = f"discovery/{plan.attempt_id}.json"
        path = self.artifact_root / relative
        _write_once(path, json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        pools = list(evidence.pool_evidence.values())
        return DiscoveryEvidence(
            status="PASS" if structurally_evaluated else "FAIL",
            eligible_rows=sum(pool.eligible_rows for pool in pools),
            covered_rows=sum(pool.covered_rows for pool in pools),
            coverage=evidence.minimum_coverage,
            daily_ic_count=min(pool.daily_ic_count for pool in pools),
            rank_ic=evidence.cross_pool_score,
            error=";".join(evidence.failures),
            artifact_path=relative,
            artifact_sha256=sha256_file(path),
        )


def feedback_row(row: dict[str, str], artifact_root: Path) -> dict[str, Any]:
    artifact: dict[str, Any] = {}
    relative = row.get("discovery_artifact_path", "")
    if relative:
        path = artifact_root / relative
        if not path.is_file() or sha256_file(path) != row["discovery_artifact_sha256"]:
            raise D1ControlError("M3-2 feedback discovery artifact differs")
        artifact = json.loads(path.read_text(encoding="utf-8"))
    semantic_status = "NOT_RUN"
    if row["parse_status"] == "PASS":
        semantic_status = (
            "FAIL" if row["failure_class"] == "semantic_contract_violation" else "PASS"
        )
    return {
        "attempt_id": row["attempt_id"],
        "global_ordinal": int(row["global_ordinal"]),
        "topic": row["topic"],
        "parse_status": row["parse_status"],
        "sandbox_status": row["sandbox_status"],
        "semantic_status": semantic_status,
        "canonical_expression": row["canonical_expression"],
        "failure_class": row["failure_class"],
        "cross_pool_min_coverage": (
            float(row["discovery_coverage"]) if row["discovery_coverage"] else None
        ),
        "cross_pool_worst_directed_rank_ic": (
            float(row["discovery_rank_ic"]) if row["discovery_rank_ic"] else None
        ),
        "cross_pool_median_directed_rank_ic": artifact.get("secondary_score"),
        "expression_tokens": int(row["expression_tokens"]) if row["expression_tokens"] else None,
        "ast_nodes": int(row["ast_nodes"]) if row["ast_nodes"] else None,
        "max_lookback_days": (
            int(row["max_lookback_days"]) if row["max_lookback_days"] else None
        ),
    }


def feedback_for_m3_attempt(
    rows: list[dict[str, str]], plan: AttemptPlan, artifact_root: Path
) -> list[dict[str, Any]]:
    if plan.evolution_mode == "independent":
        return []
    prior = [
        row
        for row in rows
        if row["topic"] == plan.topic and int(row["global_ordinal"]) < plan.global_ordinal
    ]
    return [feedback_row(row, artifact_root) for row in sorted(prior, key=lambda r: int(r["global_ordinal"]))]


def prior_expression_index(project_root: Path = PROJECT_ROOT) -> dict[str, str]:
    index: dict[str, str] = {}
    experiment_path = project_root / "ledger/experiments.csv"
    with experiment_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["candidate_source"] != "AlphaGen-GP-stage1":
                continue
            try:
                normalized = audit_expression(row["feature_or_formula"]).normalized_expression
            except (ExpressionSafetyError, ValueError):
                continue
            index.setdefault(normalized, f"stage1:{row['experiment_id']}")
    for family, relative in (
        ("d1", "ledger/llm_factor_attempts_v2.csv"),
        ("m1", "ledger/m1_star50_factor_attempts.csv"),
    ):
        with (project_root / relative).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["canonical_expression"]:
                    index.setdefault(
                        row["canonical_expression"], f"{family}:{row['attempt_id']}"
                    )
    return index


def select_m3_candidates(
    rows: list[dict[str, str]], artifact_root: Path, count: int
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if row["candidate_status"] != "DISCOVERY_EVALUATED":
            continue
        path = artifact_root / row["discovery_artifact_path"]
        if not path.is_file() or sha256_file(path) != row["discovery_artifact_sha256"]:
            raise D1ControlError("M3-2 selection artifact differs")
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("eligible") is not True:
            continue
        candidates.append({"row": row, "artifact": document})
    candidates.sort(
        key=lambda item: (
            -float(item["artifact"]["cross_pool_score"]),
            -float(item["artifact"]["secondary_score"]),
            -float(item["artifact"]["minimum_coverage"]),
            int(item["row"]["expression_tokens"]),
            int(item["row"]["global_ordinal"]),
        )
    )
    return [
        {
            "attempt_id": item["row"]["attempt_id"],
            "global_ordinal": int(item["row"]["global_ordinal"]),
            "topic": item["row"]["topic"],
            "expression_sha256": item["row"]["expression_sha256"],
            "discovery_artifact_sha256": item["row"]["discovery_artifact_sha256"],
        }
        for item in candidates[:count]
    ]
