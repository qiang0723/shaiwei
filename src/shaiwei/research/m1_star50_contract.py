"""Strict M1-1 release and immutable STAR50 discovery-input contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError, D1Protocol
from shaiwei.research.universe_registry import load_registry, registry_sha256
from shaiwei.transform.qlib_bin import QLIB_MANIFEST, qlib_tree_integrity


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _project_path(project_root: Path, value: object) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts:
        raise D1ControlError("M1-1 input path must be project-relative")
    root = project_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise D1ControlError("M1-1 input path escapes the project") from error
    if not path.is_file() and not path.is_dir():
        raise D1ControlError("M1-1 input path is missing")
    return path


@dataclass(frozen=True)
class Star50InputIdentity:
    snapshot_sha256: str
    qlib_artifact_sha256: str
    member_day_sha256: str
    discovery_rows: int
    discovery_trade_days: int


def verify_star50_inputs(protocol: D1Protocol, project_root: Path) -> Star50InputIdentity:
    """Verify frozen data identities and PIT coverage without evaluating a candidate."""
    document = protocol.document
    upstream = document["upstream_contract"]
    data = document["data_contract"]

    registry_path = _project_path(project_root, upstream["registry_path"])
    if sha256_file(registry_path) != upstream["registry_file_sha256"]:
        raise D1ControlError("M1-1 universe registry file differs from the freeze")
    registry = load_registry(registry_path, project_root=project_root)
    if registry_sha256(registry) != upstream["registry_canonical_sha256"]:
        raise D1ControlError("M1-1 universe registry canonical identity differs")
    universe = registry.universe(str(data["universe_id"]))
    if upstream["required_universe_permission"] not in universe.permissions:
        raise D1ControlError("M1-1 universe is not eligible for a new factor protocol")

    engineering_manifest = _project_path(
        project_root, upstream["p2_engineering_manifest_path"]
    )
    if sha256_file(engineering_manifest) != upstream["p2_engineering_manifest_sha256"]:
        raise D1ControlError("M1-1 P2 engineering manifest differs from the freeze")

    provider = _project_path(project_root, data["qlib_provider"])
    qlib_manifest = provider / QLIB_MANIFEST
    if sha256_file(qlib_manifest) != data["qlib_manifest_sha256"]:
        raise D1ControlError("M1-1 qlib manifest differs from the freeze")
    integrity = qlib_tree_integrity(provider)
    expected_integrity = {
        "artifact_sha256": data["qlib_artifact_sha256"],
        "artifact_file_count": int(data["qlib_artifact_file_count"]),
        "artifact_byte_count": int(data["qlib_artifact_byte_count"]),
    }
    if integrity != expected_integrity:
        raise D1ControlError("M1-1 qlib tree differs from the freeze")
    manifest = json.loads(qlib_manifest.read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in expected_integrity.items()):
        raise D1ControlError("M1-1 qlib manifest and physical tree differ")

    instrument_path = provider / f"instruments/{data['universe']}.txt"
    instruments = instrument_path.read_text(encoding="utf-8")
    if ".BJ" in instruments.upper() or any(
        line.split("\t", 1)[0].upper().startswith("BJ")
        for line in instruments.splitlines()
        if line
    ):
        raise D1ControlError("M1-1 qlib universe contains Beijing Stock Exchange members")

    member_path = _project_path(project_root, data["member_day_dataset"])
    if sha256_file(member_path) != data["member_day_dataset_sha256"]:
        raise D1ControlError("M1-1 member-day dataset differs from the freeze")
    required = {
        "trade_date",
        "ts_code",
        "has_market_bar",
        "has_daily_basic",
        "industry",
        "total_mv",
    }
    member_days = pd.read_parquet(member_path, columns=sorted(required))
    member_days["trade_date"] = pd.to_datetime(member_days["trade_date"], errors="raise")
    start, end = map(pd.Timestamp, data["requested_discovery_signal_period"])
    discovery = member_days.loc[member_days["trade_date"].between(start, end)].copy()
    counts = discovery.groupby("trade_date")["ts_code"].nunique()
    if (
        len(discovery) != int(data["discovery_member_day_rows_expected"])
        or len(counts) != int(data["discovery_trade_days_expected"])
        or counts.empty
        or not counts.eq(int(data["official_members_per_day_exact"])).all()
        or discovery.duplicated(["trade_date", "ts_code"]).any()
        or discovery["ts_code"].astype(str).str.endswith(".BJ").any()
        or int(discovery["has_market_bar"].sum())
        != int(data["discovery_market_bar_rows_expected"])
        or discovery["industry"].isna().any()
    ):
        raise D1ControlError("M1-1 discovery member-day coverage differs from the freeze")
    valid_bar = discovery["has_market_bar"].astype(bool)
    if (
        not discovery.loc[valid_bar, "has_daily_basic"].astype(bool).all()
        or not pd.to_numeric(discovery.loc[valid_bar, "total_mv"], errors="coerce").gt(0).all()
    ):
        raise D1ControlError("M1-1 discovery PIT exposures are incomplete on market bars")

    calendar = (provider / "calendars/day.txt").read_text(encoding="utf-8").splitlines()
    signal_end = str(data["requested_discovery_signal_period"][1]).replace("-", "")
    maturity = str(data["final_discovery_label_maturity_date"]).replace("-", "")
    sealed_start = str(data["sealed_validation_period"][0]).replace("-", "")
    end_index = calendar.index(signal_end)
    if calendar[end_index + int(data["horizon_trade_days"]) + 1] != maturity:
        raise D1ControlError("M1-1 final discovery label maturity differs")
    if next(day for day in calendar if day > maturity) != sealed_start:
        raise D1ControlError("M1-1 sealed validation start differs from the exchange calendar")

    payload = {
        "protocol_sha256": protocol.sha256,
        "registry_canonical_sha256": upstream["registry_canonical_sha256"],
        "p2_engineering_manifest_sha256": upstream["p2_engineering_manifest_sha256"],
        "qlib": expected_integrity,
        "qlib_manifest_sha256": data["qlib_manifest_sha256"],
        "member_day_dataset_sha256": data["member_day_dataset_sha256"],
        "discovery_signal_period": data["requested_discovery_signal_period"],
        "final_label_maturity_date": data["final_discovery_label_maturity_date"],
        "sealed_validation_period": data["sealed_validation_period"],
    }
    snapshot = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return Star50InputIdentity(
        snapshot_sha256=snapshot,
        qlib_artifact_sha256=str(integrity["artifact_sha256"]),
        member_day_sha256=sha256_file(member_path),
        discovery_rows=len(discovery),
        discovery_trade_days=len(counts),
    )


@dataclass(frozen=True)
class M1Star50ExecutionRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    total_authorization_usd: float
    batch_hard_ceiling_usd: float
    response_model_identity: str

    @classmethod
    def load(cls, path: Path, protocol: D1Protocol) -> "M1Star50ExecutionRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("M1-1 execution release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("M1-1 execution release must be a YAML object")
        if (
            document.get("schema_version") != "m1-star50-factor-execution-release-v1"
            or document.get("status") != "M1_1_RESULT_BEFORE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M1-1 execution release identity or authority differs")
        release_id = str(document.get("release_id", ""))
        if re.fullmatch(r"m1-star50-price-volume-v1-batch-[0-9]{3}", release_id) is None:
            raise D1ControlError("M1-1 execution release id is invalid")
        contract = document.get("frozen_contract", {})
        expected_contract = {
            "protocol_path": "config/m1_star50_factor_research_v1.yaml",
            "protocol_sha256": protocol.sha256,
            "prompt_sha256": protocol.prompt_bundle.sha256,
            "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
            "protocol_freeze_commit": "2ad7fd1304527343532c31951f7bbc596f186981",
        }
        if contract != expected_contract:
            raise D1ControlError("M1-1 execution release does not bind the frozen protocol")
        authorization = document.get("authorization", {})
        total = float(authorization.get("d1_total_authorization_usd", -1))
        batch = float(authorization.get("batch_hard_ceiling_usd", -1))
        if (
            int(authorization.get("completed_responses_exact", 0)) != 40
            or total != 10.0
            or batch != 1.0
            or authorization.get("future_batches_require_new_protocol_and_instruction") is not True
        ):
            raise D1ControlError("M1-1 execution release budget differs from authorization")
        expected_ledgers = {
            "attempt": "ledger/m1_star50_factor_attempts.csv",
            "transport": "ledger/m1_star50_factor_transports.csv",
            "experiment": "ledger/experiments.csv",
            "old_d1_ledgers_remain_byte_immutable": True,
        }
        if document.get("ledgers") != expected_ledgers:
            raise D1ControlError("M1-1 execution release ledger boundary differs")
        start_end = protocol.document["data_contract"]["requested_discovery_signal_period"]
        expected_scope = {
            "discovery_signal_period_only": start_end,
            "sealed_validation_access": False,
            "stress_period_access": False,
            "g1_run": False,
            "model_or_portfolio_run": False,
            "forward_access": False,
            "scheduler_changes": False,
            "web_changes": False,
            "guanxiang_access": False,
            "new_market_collection": False,
        }
        if document.get("scope") != expected_scope:
            raise D1ControlError("M1-1 execution release scope differs")
        data = protocol.document["data_contract"]
        input_contract = document.get("input_contract", {})
        if (
            input_contract.get("qlib_artifact_sha256") != data["qlib_artifact_sha256"]
            or input_contract.get("qlib_manifest_sha256") != data["qlib_manifest_sha256"]
            or input_contract.get("member_day_dataset_sha256")
            != data["member_day_dataset_sha256"]
            or re.fullmatch(r"[0-9a-f]{64}", str(input_contract.get("data_snapshot_sha256", "")))
            is None
        ):
            raise D1ControlError("M1-1 execution release input contract differs")
        if document.get("selection_contract") != {
            "run_only_after_all_40_completed_responses": True,
            "eligible_status": "DISCOVERY_EVALUATED",
            "promoted_count": 2,
            "ordering": [
                "absolute_discovery_rank_ic_desc",
                "discovery_coverage_desc",
                "expression_tokens_asc",
                "global_ordinal_asc",
            ],
            "fewer_than_two_eligible": "PAUSE",
            "sealed_validation_and_g1": "forbidden",
        }:
            raise D1ControlError("M1-1 execution release selection contract differs")
        if document.get("egress") != {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        }:
            raise D1ControlError("M1-1 execution release egress allowlist differs")
        provider = protocol.document["provider"]
        prices = protocol.document["cost_budget"]
        official = document.get("official_contract_recheck", {})
        expected_official = {
            "rechecked_on": "2026-08-01",
            "pricing_url": "https://api-docs.deepseek.com/quick_start/pricing/",
            "chat_completion_url": "https://api-docs.deepseek.com/api/create-chat-completion/",
            "model": provider["model"],
            "model_version": protocol.returned_model_identity,
            "response_model_field": provider["model"],
            "thinking": provider["thinking"],
            "reasoning_effort": provider["reasoning_effort"],
            "input_cache_hit_per_million_usd": float(
                prices["pro_input_cache_hit_per_million"]
            ),
            "input_cache_miss_per_million_usd": float(
                prices["pro_input_cache_miss_per_million"]
            ),
            "output_per_million_usd": float(prices["pro_output_per_million"]),
        }
        if official != expected_official:
            raise D1ControlError("M1-1 official provider contract differs")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=protocol.sha256,
            total_authorization_usd=total,
            batch_hard_ceiling_usd=batch,
            response_model_identity=str(official["response_model_field"]),
        )
