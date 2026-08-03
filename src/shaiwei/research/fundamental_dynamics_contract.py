"""Frozen contract and predecessor identity for the F2-0 data gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.fundamental_pit_contract import FeatureSpec, FundamentalPitError
from shaiwei.research.fundamental_pit_recovery_contract import project_relative


PROTOCOL_SCHEMA = "f2-csi800-fundamental-dynamics-v1"
PROTOCOL_ID = "f2-csi800-fundamental-dynamics-data-feature-gate-v1"
GO_VERDICT = "GO_F2_FUNDAMENTAL_DYNAMICS_DATA_FEATURE_GATE_ONLY"
NO_GO_VERDICT = "NO_GO_F2_FUNDAMENTAL_DYNAMICS_DATA_FEATURE_GATE"

EXPECTED_FEATURES = (
    ("fundamental_asset_growth_v1", "total_assets_t / total_assets_t_minus_1 - 1", -1),
    ("fundamental_revenue_growth_v1", "total_revenue_t / total_revenue_t_minus_1 - 1", 1),
    (
        "fundamental_operating_profit_change_v1",
        "(operate_profit_t - operate_profit_t_minus_1) / average_total_assets",
        1,
    ),
    (
        "fundamental_net_income_change_v1",
        "(n_income_attr_p_t - n_income_attr_p_t_minus_1) / average_total_assets",
        1,
    ),
    (
        "fundamental_operating_cashflow_change_v1",
        "(n_cashflow_act_t - n_cashflow_act_t_minus_1) / average_total_assets",
        1,
    ),
    (
        "fundamental_cash_balance_change_v1",
        "(money_cap_t - money_cap_t_minus_1) / average_total_assets",
        1,
    ),
)


@dataclass(frozen=True)
class FundamentalDynamicsProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    features: tuple[FeatureSpec, ...]

    @classmethod
    def load(cls, path: Path) -> "FundamentalDynamicsProtocol":
        if not path.is_file():
            raise FundamentalPitError("F2-0 protocol is missing")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise FundamentalPitError("F2-0 protocol must be a YAML object")
        cls._validate(document)
        features = tuple(
            FeatureSpec(
                feature_id=str(item["feature_id"]),
                formula=str(item["formula"]),
                inputs=tuple(str(value) for value in item["inputs"]),
            )
            for item in document["features"]
        )
        return cls(path=path, document=document, sha256=sha256_file(path), features=features)

    @staticmethod
    def _validate(document: dict[str, Any]) -> None:
        if document.get("schema_version") != PROTOCOL_SCHEMA or document.get("protocol_id") != PROTOCOL_ID:
            raise FundamentalPitError("F2-0 protocol identity differs from the freeze")
        _validate_scope(document.get("scope", {}))
        _validate_family(document.get("family_boundary", {}))
        _validate_sources(document.get("sources", {}))
        _validate_pit(document.get("point_in_time", {}))
        actual = tuple(
            (item.get("feature_id"), item.get("formula"), item.get("expected_direction"))
            for item in document.get("features", ())
        )
        if actual != EXPECTED_FEATURES:
            raise FundamentalPitError("F2-0 feature definitions differ from the freeze")
        if any(
            document.get(key) is not False
            for key in ("winsorization_authorized", "neutralization_authorized", "orientation_authorized")
        ):
            raise FundamentalPitError("F2-0 must not add research transformations")
        _validate_gates(document.get("gates", {}))
        outputs = document.get("outputs", {})
        if (
            outputs.get("predecessor_outputs_must_not_be_rewritten") is not True
            or outputs.get("feature_values_must_not_be_committed") is not True
        ):
            raise FundamentalPitError("F2-0 output authority differs from the freeze")
        verdicts = document.get("terminal_verdicts", {})
        expected = {"go": GO_VERDICT, "no_go": NO_GO_VERDICT, "strategy_effective": "NOT_EVALUATED"}
        if verdicts != expected:
            raise FundamentalPitError("F2-0 terminal verdicts differ from the freeze")

    @property
    def required_apis(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.document["sources"]["required_apis"])

    def project_path(self, key: str, *, project_root: Path = PROJECT_ROOT) -> Path:
        return project_relative(project_root, str(self.document["outputs"][key]))


def _validate_scope(scope: dict[str, Any]) -> None:
    expected = {
        "universe_id": "csi800-pit-v1",
        "official_index_code": "000906.SH",
        "research_family": "f2-csi800-fundamental-dynamics-v1",
        "start_date": "2016-01-01",
        "quality_start_date": "2018-05-02",
        "end_date": "2026-07-31",
        "formation_frequency": "month_end",
        "bse_included": False,
        "data_gate_only": True,
        "factor_results_authorized": False,
        "model_training_authorized": False,
        "backtest_authorized": False,
        "deepseek_authorized": False,
        "production_authorization": "none",
    }
    if scope != expected:
        raise FundamentalPitError("F2-0 authority or scope differs from the freeze")


def _validate_family(family: dict[str, Any]) -> None:
    if (
        family.get("predecessor_effect_protocol_id") != "f1-csi800-fundamental-effect-gate-v1"
        or family.get("predecessor_effect_manifest_sha256")
        != "46981c52db3c1b9321978d79c7d847e319dcf84620fe62c9f910787a4f0b8ef0"
        or family.get("predecessor_effect_verdict") != "REJECT"
        or family.get("predecessor_attempt_count") != 6
        or family.get("preserve_predecessor_without_rewrite") is not True
        or family.get("mechanism") != "consecutive_annual_fundamental_change"
        or family.get("static_level_feature_retries_forbidden") is not True
        or family.get("f2_candidate_attempt_count_if_effects_are_ever_inspected") != 6
        or family.get("cumulative_attempt_count_if_effects_are_ever_inspected") != 12
    ):
        raise FundamentalPitError("F2-0 family boundary differs from the freeze")
    forbidden = {
        "fundamental_net_income_to_assets_v2",
        "fundamental_operating_margin_v2",
        "fundamental_cash_return_on_assets_v2",
        "fundamental_leverage_v2",
        "fundamental_cash_to_assets_v2",
        "fundamental_accruals_to_assets_v2",
    }
    if set(family.get("forbidden_f1_feature_ids", ())) != forbidden:
        raise FundamentalPitError("F2-0 forbidden F1 feature set differs")


def _validate_sources(sources: dict[str, Any]) -> None:
    expected_apis = {
        "tushare.trade_cal",
        "tushare.index_weight",
        "tushare.income",
        "tushare.income_vip",
        "tushare.balancesheet",
        "tushare.balancesheet_vip",
        "tushare.cashflow",
        "tushare.cashflow_vip",
    }
    if set(sources.get("required_apis", ())) != expected_apis:
        raise FundamentalPitError("F2-0 source set differs from the freeze")
    if (
        sources.get("ledger") != "ledger/ingest_batches.csv"
        or sources.get("ledger_latest_request_wins") is not True
        or sources.get("verify_latest_batch_row_count_and_sha256") is not True
        or sources.get("network_requests_authorized") is not False
        or sources.get("raw_data_mutation_authorized") is not False
    ):
        raise FundamentalPitError("F2-0 must remain offline")


def _validate_pit(pit: dict[str, Any]) -> None:
    expected = {
        "annual_period_suffix": "1231",
        "allowed_report_types": ["1", "5"],
        "availability": "first_open_day_strictly_after_f_ann_date",
        "same_period_revision": "latest_available_f_ann_date",
        "same_announcement_report_priority": ["1", "5"],
        "same_announcement_update_priority": "descending",
        "statement_join": "exact_ts_code_and_end_date_before_period_selection",
        "pair_selection": "latest_jointly_available_consecutive_common_annual_pair",
        "predecessor_period": "exact_same_month_day_one_calendar_year_earlier",
        "combined_feature_available_date": "latest_of_all_current_and_predecessor_components",
        "newer_unpaired_period_policy": "diagnose_without_invalidating_prior_consecutive_pair",
        "current_components_cannot_mix_periods": True,
        "predecessor_components_cannot_mix_periods": True,
        "current_and_predecessor_must_be_exactly_one_year_apart": True,
        "fina_indicator_forbidden": True,
    }
    if pit != expected:
        raise FundamentalPitError("F2-0 PIT semantics differ from the freeze")


def _validate_gates(gates: dict[str, Any]) -> None:
    fixed = {
        "predecessor_identity_preserved": True,
        "required_sources_present": True,
        "required_source_columns_present": True,
        "latest_batches_integrity_pass": True,
        "source_identity_conflicts": 0,
        "open_calendar_complete_for_scope": True,
        "formation_dates_after_quality_start": "at_least_90",
        "membership_count_each_formation": {"minimum": 700, "maximum": 900},
        "bse_rows": 0,
        "duplicate_feature_keys": 0,
        "current_mixed_component_period_rows": 0,
        "predecessor_mixed_component_period_rows": 0,
        "nonconsecutive_pair_rows": 0,
        "quality_no_consecutive_pair_rows": 0,
        "future_availability_rows": 0,
        "feature_aggregate_coverage_minimum": 0.85,
        "feature_worst_formation_coverage_minimum": 0.75,
    }
    if gates != fixed:
        raise FundamentalPitError("F2-0 gates differ from the freeze")


def verify_predecessor_effect(
    protocol: FundamentalDynamicsProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    family = protocol.document["family_boundary"]
    path = project_relative(project_root, str(family["predecessor_effect_manifest"]))
    if not path.is_file() or sha256_file(path) != family["predecessor_effect_manifest_sha256"]:
        raise FundamentalPitError("F2-0 predecessor effect manifest differs")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("protocol_id") != family["predecessor_effect_protocol_id"]
        or manifest.get("verdict") != family["predecessor_effect_verdict"]
        or manifest.get("candidate_attempt_count") != family["predecessor_attempt_count"]
        or manifest.get("formal_library_insertions") != 0
    ):
        raise FundamentalPitError("F2-0 predecessor effect decision differs")
    return {
        "protocol_id": manifest["protocol_id"],
        "manifest_sha256": sha256_file(path),
        "verdict": manifest["verdict"],
        "candidate_attempt_count": manifest["candidate_attempt_count"],
        "formal_library_insertions": manifest["formal_library_insertions"],
    }
