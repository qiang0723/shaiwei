"""Frozen M6 protocol, metadata identity, and write-once evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT


M6_PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_model_attribution_v1.yaml"
ENGINEERING_PROTOCOL_PATH = (
    PROJECT_ROOT / "config/m6_csi800_model_attribution_engineering_v1.yaml"
)


class AttributionError(RuntimeError):
    """Fail-closed M6 contract, evidence, or engineering violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def project_path(value: str, *, project_root: Path = PROJECT_ROOT) -> Path:
    root = project_root.resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise AttributionError("M6 path escapes the project root")
    return path


def write_once_json(path: Path, value: Any) -> tuple[str, bool]:
    payload = canonical_json(value) + b"\n"
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if path.read_bytes() != payload:
            raise AttributionError(f"M6 write-once conflict: {path.name}")
        return digest, True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return digest, False


def _load_mapping(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AttributionError(f"M6 protocol is not a mapping: {path.name}")
    return document


def _validate_m6(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "m6-csi800-model-portfolio-attribution-small-batch-v1":
        raise AttributionError("unexpected M6 protocol identity")
    if document.get("protocol_stage") != "RESULT_BLIND_PROTOCOL_FREEZE_ONLY":
        raise AttributionError("M6 protocol stage differs")
    authority = document.get("authority", {})
    forbidden = (
        "implementation_authorized",
        "real_training_authorized",
        "prediction_authorized",
        "label_or_effect_read_authorized",
        "backtest_authorized",
        "forward_signal_authorized",
        "paper_portfolio_authorized",
        "external_network_authorized",
        "env_or_secret_read_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden):
        raise AttributionError("M6 result protocol authority was broadened")
    if authority.get("production_authorization") != "none":
        raise AttributionError("M6 result protocol cannot authorize production")
    arms = document.get("arms", [])
    expected = [
        ("clean_lgbm_control_v1", "CONTROL"),
        ("ridge_alpha1_v1", "ALTERNATIVE_1"),
        ("lgbm_ridge_rank_blend_50_50_v1", "ALTERNATIVE_2"),
    ]
    if [(row.get("arm_id"), row.get("role")) for row in arms] != expected:
        raise AttributionError("M6 frozen arm set or order differs")
    expected_control = {
        "loss": "mse",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": -1,
        "colsample_bytree": 0.8879,
        "subsample": 0.8789,
        "reg_alpha": 0.0421,
        "reg_lambda": 0.022,
        "seed": 42,
        "feature_fraction_seed": 42,
        "bagging_seed": 42,
        "data_random_seed": 42,
        "num_threads": 8,
        "deterministic": True,
        "force_col_wise": True,
        "num_boost_round": 1000,
        "early_stopping_rounds": 50,
    }
    expected_ridge = {
        "estimator": "ridge",
        "alpha": 1.0,
        "fit_intercept": False,
        "include_valid": False,
    }
    expected_blend = {
        "transform": "daily_cross_sectional_percentile_rank",
        "ascending": True,
        "tie_method": "average",
        "lgbm_weight": 0.5,
        "ridge_weight": 0.5,
        "missing_member_policy": "fail_closed_no_intersection_fallback",
    }
    if arms[0].get("parameters") != expected_control:
        raise AttributionError("M6 LightGBM parameters differ")
    if arms[1].get("parameters") != expected_ridge:
        raise AttributionError("M6 Ridge parameters differ")
    if arms[2].get("parameters") != expected_blend:
        raise AttributionError("M6 blend parameters differ")
    if document.get("scope", {}).get("formal_hypothesis_count") != 2:
        raise AttributionError("M6 requires exactly two hypotheses")
    portfolio = document.get("portfolio", {})
    expected_portfolio = {
        "topk": 30,
        "n_drop": 3,
        "rebalance_trade_days": 10,
        "deal_price": "open",
        "benchmark": "SH000906",
        "cost_multipliers": [1.0, 1.5, 2.0],
        "portfolio_variant_count": 0,
    }
    if any(portfolio.get(key) != value for key, value in expected_portfolio.items()):
        raise AttributionError("M6 frozen portfolio differs")


def _validate_engineering(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "m6-csi800-model-attribution-engineering-v1":
        raise AttributionError("unexpected M6-1 protocol identity")
    if document.get("stage") != "RESULT_BLIND_ENGINEERING_ONLY":
        raise AttributionError("M6-1 stage differs")
    authority = document.get("authority", {})
    required_false = (
        "qlib_feature_or_price_read_authorized",
        "real_model_fit_authorized",
        "real_prediction_authorized",
        "real_label_or_effect_read_authorized",
        "real_backtest_authorized",
        "experiment_ledger_write_authorized",
        "forward_signal_authorized",
        "paper_portfolio_authorized",
        "external_runtime_network_authorized",
        "env_or_secret_read_authorized",
    )
    if any(authority.get(key) is not False for key in required_false):
        raise AttributionError("M6-1 real-data or runtime authority was broadened")
    if authority.get("production_authorization") != "none":
        raise AttributionError("M6-1 cannot authorize production")
    docker = document.get("docker", {})
    if docker.get("network_mode") != "none" or docker.get("semantic_market_data_mounted") is not False:
        raise AttributionError("M6-1 Docker isolation differs")


def validate_result_document(document: dict[str, Any]) -> None:
    _validate_m6(document)


def validate_predecessor_binding(result_sha256: str, engineering: dict[str, Any]) -> None:
    if engineering.get("predecessor", {}).get("config_sha256") != result_sha256:
        raise AttributionError("M6-1 predecessor protocol hash differs")


@dataclass(frozen=True)
class ProtocolBundle:
    result_path: Path
    engineering_path: Path
    result: dict[str, Any]
    engineering: dict[str, Any]
    result_sha256: str
    engineering_sha256: str

    @classmethod
    def load(
        cls,
        result_path: Path = M6_PROTOCOL_PATH,
        engineering_path: Path = ENGINEERING_PROTOCOL_PATH,
    ) -> "ProtocolBundle":
        result_path = result_path.resolve()
        engineering_path = engineering_path.resolve()
        result = _load_mapping(result_path)
        engineering = _load_mapping(engineering_path)
        _validate_m6(result)
        _validate_engineering(engineering)
        result_sha = sha256_file(result_path)
        engineering_sha = sha256_file(engineering_path)
        validate_predecessor_binding(result_sha, engineering)
        return cls(
            result_path=result_path,
            engineering_path=engineering_path,
            result=result,
            engineering=engineering,
            result_sha256=result_sha,
            engineering_sha256=engineering_sha,
        )

    def verify_metadata_inputs(self, manifest_path: Path, calendar_path: Path) -> dict[str, Any]:
        frozen = self.result["frozen_inputs"]["qlib_provider"]
        if sha256_file(manifest_path) != frozen["manifest_sha256"]:
            raise AttributionError("M6 qlib manifest hash differs")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("artifact_sha256") != frozen["tree_sha256"]:
            raise AttributionError("M6 qlib tree identity differs")
        if int(manifest.get("artifact_file_count", -1)) != int(frozen["file_count"]):
            raise AttributionError("M6 qlib file count differs")
        calendar_lines = [line.strip() for line in calendar_path.read_text().splitlines() if line.strip()]
        if not calendar_lines or calendar_lines != sorted(set(calendar_lines)):
            raise AttributionError("M6 calendar is empty, duplicated, or unsorted")
        return {
            "qlib_manifest_sha256": frozen["manifest_sha256"],
            "qlib_tree_sha256": frozen["tree_sha256"],
            "qlib_file_count": int(frozen["file_count"]),
            "calendar_row_count": len(calendar_lines),
            "semantic_market_rows_read": False,
        }
