"""D1-2B bounded live generation and discovery-only evaluation runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import socket
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.benchmark.alphagen_cpu import (
    _load_exposures,
    _verify_vendor_checkout,
    stock_data_effective_start,
)
from shaiwei.benchmark.fitness import neutralized_rank_ic
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import ingest_snapshot_sha256, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.alphagen_expression import parse_safe_expression
from shaiwei.research.deepseek_client import (
    D1ExecutionRelease,
    TRANSPORT_LEDGER_HEADER_V2,
    create_live_deepseek_provider,
)
from shaiwei.research.llm_factor import (
    ATTEMPT_LEDGER_HEADER_V2,
    D1ControlError,
    D1Protocol,
    DiscoveryEvidence,
    AttemptPlan,
    execute_completed_attempt,
    plan_attempt,
    verify_attempt_experiment_bijection,
)
from shaiwei.transform.qlib_bin import QLIB_MANIFEST, qlib_tree_integrity


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable D1-2B artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ATTEMPT_LEDGER_HEADER_V2:
            raise D1ControlError("D1 attempt ledger schema differs from the live runner")
        rows = list(reader)
    ids = [row["attempt_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise D1ControlError("D1 attempt ledger contains duplicate ids")
    return rows


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


def _optional_int(value: str) -> int | None:
    return int(value) if value else None


def feedback_for_attempt(rows: list[dict[str, str]], plan: AttemptPlan) -> list[dict[str, Any]]:
    """Serialize every prior same-topic attempt from immutable ledger fields only."""
    prior = [
        row
        for row in rows
        if row["topic"] == plan.topic and int(row["global_ordinal"]) < plan.global_ordinal
    ]
    prior.sort(key=lambda row: int(row["global_ordinal"]))
    if plan.evolution_mode == "independent":
        if prior:
            raise D1ControlError("independent D1 attempt unexpectedly has prior same-topic rows")
        return []
    return [
        {
            "attempt_id": row["attempt_id"],
            "global_ordinal": int(row["global_ordinal"]),
            "topic": row["topic"],
            "parse_status": row["parse_status"],
            "sandbox_status": row["sandbox_status"],
            "canonical_expression": row["canonical_expression"],
            "duplicate_of_attempt_id": row["duplicate_of_attempt_id"],
            "failure_class": row["failure_class"],
            "discovery_coverage": _optional_float(row["discovery_coverage"]),
            "discovery_rank_ic": _optional_float(row["discovery_rank_ic"]),
            "expression_tokens": _optional_int(row["expression_tokens"]),
            "ast_nodes": _optional_int(row["ast_nodes"]),
            "max_lookback_days": _optional_int(row["max_lookback_days"]),
        }
        for row in prior
    ]


def _finite_rows(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in columns:
        mask &= np.isfinite(pd.to_numeric(frame[column], errors="coerce"))
    return mask


@dataclass
class DiscoveryEvaluator:
    protocol: D1Protocol
    release: D1ExecutionRelease
    artifact_root: Path

    def __post_init__(self) -> None:
        settings = load()
        contract = self.release.document["discovery_contract"]
        current_ingest = ingest_snapshot_sha256()
        if current_ingest != contract["ingest_snapshot_sha256_at_freeze"]:
            raise D1ControlError("D1 discovery ingest snapshot differs from the result-before freeze")
        provider = PROJECT_ROOT / str(contract["qlib_provider"])
        manifest_path = provider / QLIB_MANIFEST
        if sha256_file(manifest_path) != contract["qlib_manifest_sha256"]:
            raise D1ControlError("D1 qlib manifest differs from the result-before freeze")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        integrity = qlib_tree_integrity(provider)
        expected_integrity = {
            "artifact_sha256": contract["qlib_artifact_sha256"],
            "artifact_file_count": int(contract["qlib_artifact_file_count"]),
            "artifact_byte_count": int(contract["qlib_artifact_byte_count"]),
        }
        if any(integrity[key] != value for key, value in expected_integrity.items()):
            raise D1ControlError("D1 qlib tree differs from the result-before freeze")
        if any(manifest.get(key) != value for key, value in expected_integrity.items()):
            raise D1ControlError("D1 qlib manifest and tree identities differ")
        instruments = (provider / "instruments/csi800.txt").read_text(encoding="utf-8")
        if ".BJ" in instruments.upper() or any(
            line.split("\t", 1)[0].upper().startswith("BJ")
            for line in instruments.splitlines()
            if line
        ):
            raise D1ControlError("D1 discovery universe contains Beijing Stock Exchange members")

        vendor = PROJECT_ROOT / "vendor/alphagen"
        self.vendor_commit = _verify_vendor_checkout(vendor)
        sys.path.insert(0, str(vendor))
        from alphagen.data.expression import Ref
        from alphagen_qlib import stock_data as alphagen_stock_data
        from alphagen_qlib.stock_data import StockData
        from alphagen_generic.features import open_

        initialize_qlib(settings, provider_uri=provider)
        alphagen_stock_data._QLIB_INITIALIZED = True
        start = pd.Timestamp(
            self.release.document["scope"]["discovery_period_only"][0]
        ).date()
        end = pd.Timestamp(self.release.document["scope"]["discovery_period_only"][1]).date()
        effective_start = stock_data_effective_start(start, 100)
        if effective_start != start:
            raise D1ControlError("D1 discovery start moved after the result-before freeze")
        self.data = StockData(
            str(contract["universe"]),
            start.isoformat(),
            end.isoformat(),
            max_backtrack_days=100,
            max_future_days=settings.backtest.rebalance_days + 1,
            device=torch.device("cpu"),
        )
        target = Ref(open_, -(settings.backtest.rebalance_days + 1)) / Ref(open_, -1) - 1
        label = self.data.make_dataframe(target.evaluate(self.data), columns=["label"]).reset_index()
        label.columns = ["trade_date", "instrument", "label"]
        exposures = _load_exposures(
            set(label["instrument"].dropna().astype(str)),
            start,
            end,
        )
        eligible = label.merge(exposures, on=["trade_date", "instrument"], how="inner")
        valid = _finite_rows(eligible, ("label", "market_cap"))
        valid &= eligible["market_cap"].gt(0) & eligible["industry"].notna()
        self.label = label
        self.exposures = exposures
        self.eligible = eligible.loc[valid].copy()
        self.minimum_cross_section = int(contract["minimum_cross_section"])
        self.minimum_daily_ic = int(contract["minimum_daily_ic_observations"])
        self.data_snapshot_sha256 = _sha256_text(
            _canonical_json(
                {
                    "ingest_snapshot_sha256": current_ingest,
                    "qlib_artifact_sha256": integrity["artifact_sha256"],
                    "qlib_manifest_sha256": contract["qlib_manifest_sha256"],
                    "period": self.release.document["scope"]["discovery_period_only"],
                    "universe": contract["universe"],
                }
            )
        )

    def __call__(self, plan: AttemptPlan, expression: str) -> DiscoveryEvidence:
        evaluated = parse_safe_expression(expression).evaluate(self.data)
        factor = self.data.make_dataframe(evaluated, columns=["factor"]).reset_index()
        factor.columns = ["trade_date", "instrument", "factor"]
        observations = factor.merge(self.label, on=["trade_date", "instrument"], how="inner").merge(
            self.exposures,
            on=["trade_date", "instrument"],
            how="inner",
        )
        eligible_rows = len(self.eligible)
        covered = observations.loc[
            _finite_rows(observations, ("factor", "label", "market_cap"))
            & observations["market_cap"].gt(0)
            & observations["industry"].notna()
        ].copy()
        covered_rows = len(covered)
        coverage = covered_rows / eligible_rows if eligible_rows else None
        rank_ic, daily_ic = neutralized_rank_ic(observations, self.minimum_cross_section)
        finite_rank_ic = float(rank_ic) if math.isfinite(float(rank_ic)) else None
        passed = len(daily_ic) >= self.minimum_daily_ic and finite_rank_ic is not None
        error = "" if passed else f"insufficient_daily_ic:{len(daily_ic)}"
        artifact = {
            "schema_version": "d1-discovery-evidence-v1",
            "attempt_id": plan.attempt_id,
            "global_ordinal": plan.global_ordinal,
            "topic": plan.topic,
            "expression": expression,
            "data_snapshot_sha256": self.data_snapshot_sha256,
            "eligible_rows": eligible_rows,
            "covered_rows": covered_rows,
            "coverage": coverage,
            "minimum_cross_section": self.minimum_cross_section,
            "minimum_daily_ic_observations": self.minimum_daily_ic,
            "daily_ic_count": len(daily_ic),
            "rank_ic": finite_rank_ic if passed else None,
            "error": error,
            "daily_ic": [
                {"trade_date": pd.Timestamp(date).date().isoformat(), "rank_ic": float(value)}
                for date, value in daily_ic.items()
            ],
            "W1_W6_read": False,
            "stress_periods_read": False,
            "g1_run": False,
        }
        relative = f"discovery/{plan.attempt_id}.json"
        path = self.artifact_root / relative
        _write_once(path, json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return DiscoveryEvidence(
            status="PASS" if passed else "FAIL",
            eligible_rows=eligible_rows,
            covered_rows=covered_rows,
            coverage=coverage,
            daily_ic_count=len(daily_ic),
            rank_ic=finite_rank_ic if passed else None,
            error=error,
            artifact_path=relative,
            artifact_sha256=sha256_file(path),
        )


def tls_hostname_probe(release: D1ExecutionRelease) -> str:
    egress = release.document["egress"]
    host = str(egress["host"])
    port = int(egress["port"])
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=host) as connection:
            certificate = connection.getpeercert(binary_form=True)
            if not certificate:
                raise D1ControlError("D1 TLS probe returned no peer certificate")
    return hashlib.sha256(certificate).hexdigest()


def _selection(rows: list[dict[str, str]], count: int) -> list[dict[str, Any]]:
    eligible = [row for row in rows if row["candidate_status"] == "DISCOVERY_EVALUATED"]
    eligible.sort(
        key=lambda row: (
            -abs(float(row["discovery_rank_ic"])),
            -float(row["discovery_coverage"]),
            int(row["expression_tokens"]),
            int(row["global_ordinal"]),
        )
    )
    return [
        {
            "attempt_id": row["attempt_id"],
            "global_ordinal": int(row["global_ordinal"]),
            "topic": row["topic"],
            "expression_sha256": row["expression_sha256"],
            "discovery_artifact_sha256": row["discovery_artifact_sha256"],
        }
        for row in eligible[:count]
    ]


def verify_static_evidence(
    *,
    release: D1ExecutionRelease,
    attempt_rows: list[dict[str, str]],
    transport_ledger_path: Path,
    artifact_root: Path,
) -> dict[str, int]:
    """Re-hash immutable D1-2B artifacts without data, network, or secret access."""
    batch = [row for row in attempt_rows if row["execution_release_id"] == release.release_id]
    if len(batch) != 40 or [int(row["global_ordinal"]) for row in batch] != list(range(1, 41)):
        raise D1ControlError("D1 static evidence does not contain the exact completed batch")
    artifact_root_resolved = artifact_root.resolve()

    def verified(relative: str, expected_sha256: str, *, root: Path = artifact_root) -> None:
        path_value = Path(relative)
        if path_value.is_absolute():
            raise D1ControlError("D1 evidence artifact path must be relative")
        path = (root / path_value).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as error:
            raise D1ControlError("D1 evidence artifact escapes its root") from error
        if not path.is_file() or sha256_file(path) != expected_sha256:
            raise D1ControlError("D1 evidence artifact is missing or changed")

    raw_count = 0
    discovery_count = 0
    for row in batch:
        if row["execution_release_sha256"] != release.sha256:
            raise D1ControlError("D1 attempt release identity differs")
        verified(row["artifact_manifest_path"], row["artifact_manifest_sha256"])
        manifest_path = artifact_root_resolved / row["artifact_manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_relative = str(manifest.get("raw_response_path", ""))
        if raw_relative:
            verified(raw_relative, row["response_sha256"])
            raw_count += 1
        if row["discovery_artifact_path"]:
            verified(row["discovery_artifact_path"], row["discovery_artifact_sha256"])
            discovery_count += 1

    with transport_ledger_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
            raise D1ControlError("D1 transport v2 ledger schema differs")
        events = list(reader)
    event_ids = [row["event_id"] for row in events]
    if len(event_ids) != len(set(event_ids)):
        raise D1ControlError("D1 transport v2 ledger contains duplicate event ids")
    if any(row["execution_release_sha256"] != release.sha256 for row in events):
        raise D1ControlError("D1 transport release identity differs")
    if any(row["event_type"] == "BILLING_UNCERTAIN" for row in events):
        raise D1ControlError("D1 transport contains unresolved billing uncertainty")
    completed = [row for row in events if row["event_type"] == "COMPLETED"]
    if len(completed) != 40 or {row["attempt_id"] for row in completed} != {
        row["attempt_id"] for row in batch
    }:
        raise D1ControlError("D1 transport completions do not match the attempt ledger")
    provider_root = artifact_root / "provider"
    for event in completed:
        verified(
            event["response_artifact_path"],
            event["response_artifact_sha256"],
            root=provider_root,
        )
    return {
        "attempt_rows": len(batch),
        "transport_events": len(events),
        "transport_completions": len(completed),
        "raw_response_artifacts": raw_count,
        "discovery_artifacts": discovery_count,
    }


def _report(
    *,
    protocol: D1Protocol,
    release: D1ExecutionRelease,
    rows: list[dict[str, str]],
    evaluator: DiscoveryEvaluator,
    code_sha256: str,
    release_git_head: str,
    tls_certificate_sha256: str,
) -> dict[str, Any]:
    batch = [row for row in rows if row["execution_release_id"] == release.release_id]
    selected = _selection(batch, int(release.document["selection_contract"]["promoted_count"]))
    cost = sum(float(row["estimated_cost_usd"]) for row in batch)
    return {
        "schema_version": "d1-llm-factor-live-run-report-v1",
        "release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "protocol_sha256": protocol.sha256,
        "prompt_sha256": protocol.prompt_bundle.sha256,
        "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
        "code_snapshot_sha256": code_sha256,
        "release_git_head": release_git_head,
        "data_snapshot_sha256": evaluator.data_snapshot_sha256,
        "qlib_artifact_sha256": release.document["discovery_contract"]["qlib_artifact_sha256"],
        "tls_certificate_sha256": tls_certificate_sha256,
        "completed_response_count": len(batch),
        "completed_response_exact_gate": len(batch) == 40,
        "global_ordinals_complete": [int(row["global_ordinal"]) for row in batch]
        == list(range(1, 41)),
        "attempt_experiment_bijection": verify_attempt_experiment_bijection(
            PROJECT_ROOT / release.document["ledgers"]["attempt"],
            PROJECT_ROOT / release.document["ledgers"]["experiment"],
        ),
        "actual_cost_usd": cost,
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "d1_total_authorization_usd": release.total_authorization_usd,
        "cost_gate_pass": cost <= release.batch_hard_ceiling_usd,
        "candidate_status_counts": {
            status: sum(row["candidate_status"] == status for row in batch)
            for status in sorted({row["candidate_status"] for row in batch})
        },
        "failure_class_counts": {
            status or "NONE": sum(row["failure_class"] == status for row in batch)
            for status in sorted({row["failure_class"] for row in batch})
        },
        "selected_count": len(selected),
        "mechanical_top2": selected,
        "d1_2b_verdict": "GO_D1_3_REVIEW" if len(selected) == 2 else "PAUSE",
        "discovery_results_evaluated": True,
        "W1_W6_read": False,
        "stress_periods_read": False,
        "g1_run": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def run_live(
    *,
    protocol_path: Path,
    release_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    protocol = D1Protocol.load(protocol_path)
    release = D1ExecutionRelease.load(release_path, protocol)
    code_sha = code_snapshot_sha256()
    release_head = git_head()
    ledger_path = PROJECT_ROOT / release.document["ledgers"]["attempt"]
    experiment_ledger_path = PROJECT_ROOT / release.document["ledgers"]["experiment"]
    transport_ledger_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    artifact_root = output_root / "artifacts"
    report_path = output_root / "d1_2b_run_report.json"
    existing = _rows(ledger_path)
    batch_existing = [row for row in existing if row["execution_release_id"] == release.release_id]
    if len(batch_existing) == 40 and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("completed_response_count") != 40:
            raise D1ControlError("D1 completed report differs from its attempt ledger")
        static = verify_static_evidence(
            release=release,
            attempt_rows=existing,
            transport_ledger_path=transport_ledger_path,
            artifact_root=artifact_root,
        )
        if report.get("static_evidence") != static:
            raise D1ControlError("D1 completed report differs from re-hashed static evidence")
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
    if any(row["execution_release_id"] not in {"", release.release_id} for row in existing):
        raise D1ControlError("D1 attempt ledger contains a different live execution release")
    if [int(row["global_ordinal"]) for row in batch_existing] != list(
        range(1, len(batch_existing) + 1)
    ):
        raise D1ControlError("D1 partial live batch is not a contiguous prefix")

    evaluator = DiscoveryEvaluator(protocol, release, artifact_root)
    tls_certificate_sha256 = tls_hostname_probe(release)
    external_calls = 0
    for ordinal in range(1, 41):
        plan = plan_attempt(protocol, ordinal)
        current_rows = _rows(ledger_path)
        feedback = feedback_for_attempt(current_rows, plan)
        with create_live_deepseek_provider(
            protocol,
            execution_release=release,
            attempt_id=plan.attempt_id,
            transport_ledger_path=transport_ledger_path,
            artifact_root=artifact_root / "provider",
            operator="docker-d1-live",
        ) as provider:
            result = execute_completed_attempt(
                protocol,
                plan,
                provider,
                ledger_path=ledger_path,
                experiment_ledger_path=experiment_ledger_path,
                artifact_root=artifact_root,
                operator="docker-d1-live",
                code_sha256=code_sha,
                feedback_records=feedback,
                execution_release_id=release.release_id,
                execution_release_sha256=release.sha256,
                cost_hard_ceiling_usd=release.batch_hard_ceiling_usd,
                data_sha256=evaluator.data_snapshot_sha256,
                discovery_evaluator=evaluator,
                returned_model_identity=release.response_model_identity,
            )
            external_calls += provider.external_api_calls
        print(
            _canonical_json(
                {
                    "global_ordinal": ordinal,
                    "completed": True,
                    "candidate_status": result.row["candidate_status"],
                    "failure_class": result.row["failure_class"] or "NONE",
                    "cumulative_cost_usd": round(
                        sum(float(row["estimated_cost_usd"]) for row in _rows(ledger_path)), 8
                    ),
                }
            ),
            flush=True,
        )
        if result.row["failure_class"] in {
            "cost_budget_exceeded",
            "model_identity_mismatch",
            "sensitive_output",
            "usage_missing_or_invalid",
            "discovery_evaluation_error",
        }:
            raise D1ControlError("D1 live batch stopped at a fatal completed-response gate")

    final_rows = _rows(ledger_path)
    report = _report(
        protocol=protocol,
        release=release,
        rows=final_rows,
        evaluator=evaluator,
        code_sha256=code_sha,
        release_git_head=release_head,
        tls_certificate_sha256=tls_certificate_sha256,
    )
    report["static_evidence"] = verify_static_evidence(
        release=release,
        attempt_rows=final_rows,
        transport_ledger_path=transport_ledger_path,
        artifact_root=artifact_root,
    )
    if not (
        report["completed_response_exact_gate"]
        and report["global_ordinals_complete"]
        and report["cost_gate_pass"]
    ):
        raise D1ControlError("D1 live batch failed its terminal machine gates")
    _write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/d1_llm_factor_research_v1.yaml",
    )
    parser.add_argument(
        "--execution-release",
        type=Path,
        default=PROJECT_ROOT / "config/d1_llm_factor_execution_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "data/research/d1/d1-llm-dsl-v1",
    )
    args = parser.parse_args(argv)
    try:
        report = run_live(
            protocol_path=args.protocol,
            release_path=args.execution_release,
            output_root=args.output_root,
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(_canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
