"""Frozen F1-0 protocol and immutable source identity verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import INGEST, resolve_artifact_path, sha256_file


PROTOCOL_SCHEMA = "f1-csi800-fundamental-pit-v1"
PROTOCOL_ID = "f1-csi800-fundamental-pit-data-feature-gate-v1"
GO_VERDICT = "GO_F1_FUNDAMENTAL_PIT_DATA_FEATURE_GATE_ONLY"
NO_GO_VERDICT = "NO_GO_F1_FUNDAMENTAL_PIT_DATA_FEATURE_GATE"


class FundamentalPitError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    formula: str
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class FundamentalPitProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    features: tuple[FeatureSpec, ...]

    @classmethod
    def load(cls, path: Path) -> "FundamentalPitProtocol":
        if not path.is_file():
            raise FundamentalPitError("F1-0 protocol is missing")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise FundamentalPitError("F1-0 protocol must be a YAML object")
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
            raise FundamentalPitError("F1-0 protocol identity differs from the freeze")
        scope = document.get("scope", {})
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
        if any(scope.get(key) != value for key, value in expected_scope.items()):
            raise FundamentalPitError("F1-0 authority or date boundary differs from the freeze")
        sources = document.get("sources", {})
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
            raise FundamentalPitError("F1-0 source set differs from the freeze")
        if sources.get("network_requests_authorized") is not False:
            raise FundamentalPitError("F1-0 must remain offline")
        pit = document.get("point_in_time", {})
        if (
            pit.get("annual_period_suffix") != "1231"
            or pit.get("availability") != "first_open_day_strictly_after_f_ann_date"
            or pit.get("current_components_cannot_mix_periods") is not True
            or pit.get("fina_indicator_forbidden") is not True
        ):
            raise FundamentalPitError("F1-0 PIT contract differs from the freeze")
        features = document.get("features", ())
        expected_features = (
            ("fundamental_net_income_to_assets_v1", "n_income_attr_p / total_assets"),
            ("fundamental_operating_margin_v1", "operate_profit / total_revenue"),
            ("fundamental_cash_return_on_assets_v1", "n_cashflow_act / total_assets"),
            ("fundamental_leverage_v1", "total_liab / total_assets"),
            ("fundamental_cash_to_assets_v1", "money_cap / total_assets"),
            ("fundamental_accruals_to_assets_v1", "(n_income_attr_p - n_cashflow_act) / total_assets"),
        )
        actual_features = tuple((item.get("feature_id"), item.get("formula")) for item in features)
        if actual_features != expected_features:
            raise FundamentalPitError("F1-0 feature definitions differ from the freeze")
        if (
            document.get("winsorization_authorized") is not False
            or document.get("neutralization_authorized") is not False
            or document.get("direction_authorized") is not False
        ):
            raise FundamentalPitError("F1-0 must not add research transformations")
        verdicts = document.get("terminal_verdicts", {})
        if verdicts != {"go": GO_VERDICT, "no_go": NO_GO_VERDICT, "strategy_effective": "NOT_EVALUATED"}:
            raise FundamentalPitError("F1-0 terminal verdicts differ from the freeze")

    @property
    def required_apis(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.document["sources"]["required_apis"])

    def project_path(self, key: str, *, project_root: Path = PROJECT_ROOT) -> Path:
        value = Path(str(self.document["outputs"][key]))
        if value.is_absolute() or ".." in value.parts:
            raise FundamentalPitError("F1-0 output path must be project-relative")
        result = (project_root.resolve() / value).resolve()
        try:
            result.relative_to(project_root.resolve())
        except ValueError as error:
            raise FundamentalPitError("F1-0 output path escapes project") from error
        return result


def _latest_entries(entries: pd.DataFrame, source_api: str) -> pd.DataFrame:
    selected = entries.loc[entries["source_api"].eq(source_api)].copy()
    if selected.empty:
        raise FundamentalPitError(f"missing committed source: {source_api}")
    selected["_params_key"] = selected["params_json"].map(
        lambda value: canonical_json(json.loads(str(value)))
    )
    selected["_time"] = pd.to_datetime(selected["ingest_time"], utc=True, errors="raise")
    return selected.sort_values(["_time", "batch_id"]).drop_duplicates("_params_key", keep="last")


def verify_source_evidence(
    protocol: FundamentalPitProtocol,
    *,
    ledger_path: Path = INGEST,
) -> dict[str, dict[str, int | str]]:
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    evidence: dict[str, dict[str, int | str]] = {}
    for source_api in protocol.required_apis:
        latest = _latest_entries(entries, source_api)
        identities = []
        total_rows = 0
        for row in latest.itertuples(index=False):
            path = resolve_artifact_path(row.parquet_path)
            if not path.is_file():
                raise FundamentalPitError(f"committed F1-0 batch is missing: {source_api}")
            metadata = pq.read_metadata(path)
            expected_rows = int(row.row_count)
            if metadata.num_rows != expected_rows or sha256_file(path) != row.content_sha256:
                raise FundamentalPitError(f"committed F1-0 batch failed integrity: {source_api}")
            total_rows += expected_rows
            identities.append(
                {
                    "batch_id": str(row.batch_id),
                    "params": json.loads(str(row.params_json)),
                    "row_count": expected_rows,
                    "content_sha256": str(row.content_sha256),
                }
            )
        evidence[source_api] = {
            "request_count": len(latest),
            "row_count": total_rows,
            "snapshot_sha256": sha256_json(identities),
        }
    return evidence
