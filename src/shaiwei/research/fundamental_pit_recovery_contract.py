"""Frozen contract for the F1-0R latest-common-period PIT recovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.fundamental_pit_contract import FeatureSpec, FundamentalPitError


PROTOCOL_SCHEMA = "f1-csi800-fundamental-pit-recovery-v2"
PROTOCOL_ID = "f1-csi800-fundamental-pit-recovery-data-feature-gate-v2"
GO_VERDICT = "GO_F1_FUNDAMENTAL_PIT_RECOVERY_DATA_FEATURE_GATE_ONLY"
NO_GO_VERDICT = "NO_GO_F1_FUNDAMENTAL_PIT_RECOVERY_DATA_FEATURE_GATE"


@dataclass(frozen=True)
class FundamentalPitRecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    features: tuple[FeatureSpec, ...]

    @classmethod
    def load(cls, path: Path) -> "FundamentalPitRecoveryProtocol":
        if not path.is_file():
            raise FundamentalPitError("F1-0R protocol is missing")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise FundamentalPitError("F1-0R protocol must be a YAML object")
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
            raise FundamentalPitError("F1-0R protocol identity differs from the freeze")
        predecessor = document.get("predecessor", {})
        expected_predecessor = {
            "protocol_id": "f1-csi800-fundamental-pit-data-feature-gate-v1",
            "verdict": "NO_GO_F1_FUNDAMENTAL_PIT_DATA_FEATURE_GATE",
            "tracked_manifest": "config/f1_csi800_fundamental_pit_manifest_v1.json",
            "tracked_manifest_sha256": "6f99c434b5447a019b400cff534c0ce55cd40010ab53b34b29c18f002e9297d3",
            "feature_panel_sha256": "7475aab079d980c76f0e2bb5eb7fa6139b83a43f53dd6c8aafbbf74a3a30d89e",
            "quality_report_sha256": "57d2c40bc6ea231c6d5ec26502853ea9ce8e8a63abe616c14269d57f027affb8",
            "preserve_without_rewrite": True,
        }
        if predecessor != expected_predecessor:
            raise FundamentalPitError("F1-0R predecessor identity differs from the freeze")
        expected_scope = {
            "universe_id": "csi800-pit-v1",
            "official_index_code": "000906.SH",
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
        if document.get("scope") != expected_scope:
            raise FundamentalPitError("F1-0R authority or scope differs from the freeze")
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
        sources = document.get("sources", {})
        if set(sources.get("required_apis", ())) != expected_apis:
            raise FundamentalPitError("F1-0R source set differs from the freeze")
        if (
            sources.get("ledger") != "ledger/ingest_batches.csv"
            or sources.get("ledger_latest_request_wins") is not True
            or sources.get("verify_latest_batch_row_count_and_sha256") is not True
            or sources.get("network_requests_authorized") is not False
            or sources.get("raw_data_mutation_authorized") is not False
        ):
            raise FundamentalPitError("F1-0R must remain offline")
        pit = document.get("point_in_time", {})
        expected_pit = {
            "annual_period_suffix": "1231",
            "allowed_report_types": ["1", "5"],
            "availability": "first_open_day_strictly_after_f_ann_date",
            "same_period_revision": "latest_available_f_ann_date",
            "same_announcement_report_priority": ["1", "5"],
            "same_announcement_update_priority": "descending",
            "statement_join": "exact_ts_code_and_end_date_before_period_selection",
            "formation_period_selection": "latest_jointly_available_common_end_date",
            "combined_feature_available_date": "latest_component_available_date",
            "newer_unmatched_statement_policy": "diagnose_without_invalidating_prior_common_period",
            "current_components_cannot_mix_periods": True,
            "fina_indicator_forbidden": True,
        }
        if pit != expected_pit:
            raise FundamentalPitError("F1-0R PIT semantics differ from the freeze")
        expected_features = (
            ("fundamental_net_income_to_assets_v2", "n_income_attr_p / total_assets"),
            ("fundamental_operating_margin_v2", "operate_profit / total_revenue"),
            ("fundamental_cash_return_on_assets_v2", "n_cashflow_act / total_assets"),
            ("fundamental_leverage_v2", "total_liab / total_assets"),
            ("fundamental_cash_to_assets_v2", "money_cap / total_assets"),
            ("fundamental_accruals_to_assets_v2", "(n_income_attr_p - n_cashflow_act) / total_assets"),
        )
        actual_features = tuple(
            (item.get("feature_id"), item.get("formula")) for item in document.get("features", ())
        )
        if actual_features != expected_features:
            raise FundamentalPitError("F1-0R feature definitions differ from the freeze")
        if any(
            document.get(key) is not False
            for key in ("winsorization_authorized", "neutralization_authorized", "direction_authorized")
        ):
            raise FundamentalPitError("F1-0R must not add research transformations")
        expected_gates = {
            "predecessor_identity_preserved": True,
            "required_sources_present": True,
            "required_source_columns_present": True,
            "latest_batches_integrity_pass": True,
            "source_identity_conflicts": 0,
            "open_calendar_complete_for_scope": True,
            "formation_dates_after_quality_start": "at_least_90",
            "membership_count_each_formation": {"minimum": 700, "maximum": 900},
            "bse_rows": 0,
            "constructed_mixed_component_period_rows": 0,
            "quality_no_common_period_rows": 0,
            "future_availability_rows": 0,
            "feature_aggregate_coverage_minimum": 0.90,
            "feature_worst_formation_coverage_minimum": 0.80,
        }
        if document.get("gates") != expected_gates:
            raise FundamentalPitError("F1-0R gates differ from the freeze")
        outputs = document.get("outputs", {})
        if (
            outputs.get("predecessor_outputs_must_not_be_rewritten") is not True
            or outputs.get("feature_values_must_not_be_committed") is not True
        ):
            raise FundamentalPitError("F1-0R output authority differs from the freeze")
        verdicts = document.get("terminal_verdicts", {})
        if verdicts != {"go": GO_VERDICT, "no_go": NO_GO_VERDICT, "strategy_effective": "NOT_EVALUATED"}:
            raise FundamentalPitError("F1-0R terminal verdicts differ from the freeze")

    @property
    def required_apis(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.document["sources"]["required_apis"])

    def project_path(self, key: str, *, project_root: Path = PROJECT_ROOT) -> Path:
        return project_relative(project_root, str(self.document["outputs"][key]))


def project_relative(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise FundamentalPitError("F1-0R path must be project-relative")
    result = (project_root.resolve() / path).resolve()
    try:
        result.relative_to(project_root.resolve())
    except ValueError as error:
        raise FundamentalPitError("F1-0R path escapes project") from error
    return result


def verify_predecessor(
    protocol: FundamentalPitRecoveryProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, str]:
    expected = protocol.document["predecessor"]
    manifest_path = project_relative(project_root, str(expected["tracked_manifest"]))
    if not manifest_path.is_file() or sha256_file(manifest_path) != expected["tracked_manifest_sha256"]:
        raise FundamentalPitError("F1-0R predecessor tracked manifest differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != expected["protocol_id"] or manifest.get("verdict") != expected["verdict"]:
        raise FundamentalPitError("F1-0R predecessor verdict identity differs")
    feature = manifest.get("feature_panel", {})
    report = manifest.get("report", {})
    if feature.get("sha256") != expected["feature_panel_sha256"]:
        raise FundamentalPitError("F1-0R predecessor feature identity differs")
    if report.get("sha256") != expected["quality_report_sha256"]:
        raise FundamentalPitError("F1-0R predecessor report identity differs")
    feature_path = project_relative(project_root, str(feature.get("path", "")))
    report_path = project_relative(project_root, str(report.get("path", "")))
    if not feature_path.is_file() or sha256_file(feature_path) != expected["feature_panel_sha256"]:
        raise FundamentalPitError("F1-0R predecessor feature file was rewritten")
    if not report_path.is_file() or sha256_file(report_path) != expected["quality_report_sha256"]:
        raise FundamentalPitError("F1-0R predecessor report file was rewritten")
    return {
        "protocol_id": str(expected["protocol_id"]),
        "verdict": str(expected["verdict"]),
        "tracked_manifest_sha256": str(expected["tracked_manifest_sha256"]),
        "feature_panel_sha256": str(expected["feature_panel_sha256"]),
        "quality_report_sha256": str(expected["quality_report_sha256"]),
    }
