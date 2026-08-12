"""Frozen TS-1A protocol and immutable artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v3_data_gate_v1.yaml"
OUTPUT_DIR = PROJECT_ROOT / "data/research/trend_swing/ts-v3-data-gate-v1"
REPORT_PATH = OUTPUT_DIR / "profile_report.json"
MANIFEST_PATH = OUTPUT_DIR / "input_manifest.json"
AUDIT_PATH = OUTPUT_DIR / "audit.json"
ALPHA158_PATH = (
    PROJECT_ROOT
    / "data/research/moneyflow/residuals/p1-moneyflow-alpha158-predictions-v1-46a24aad0c21e2df.parquet"
)

FORBIDDEN_RESULT_TERMS = {
    "return_after_entry",
    "win_rate",
    "pnl",
    "excess_return",
    "mae",
    "mfe",
    "sharpe",
    "drawdown",
    "stock_recommendation",
}


class TrendSwingError(RuntimeError):
    """Fail-closed TS contract, data, or evidence violation."""


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(value: str | Path, *, root: Path = PROJECT_ROOT) -> Path:
    base = root.resolve()
    path = (base / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if not path.is_relative_to(base):
        raise TrendSwingError("TS path escapes the project root")
    return path


def write_once_json(path: Path, value: Any) -> tuple[str, bool]:
    project_path(path)
    payload = canonical_json(value) + b"\n"
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if path.read_bytes() != payload:
            raise TrendSwingError(f"TS write-once conflict: {path.name}")
        return digest, True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return digest, False


def _require_false(document: dict[str, Any], names: tuple[str, ...]) -> None:
    authority = document.get("authorization", {})
    if any(authority.get(name) is not False for name in names):
        raise TrendSwingError("TS-1A forbidden authority was broadened")


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "ts-v3-result-blind-data-gate-v1":
        raise TrendSwingError("unexpected TS-1A protocol identity")
    if document.get("stage") != "RESULT_BLIND_QUANTIFICATION_AND_DATA_GATE_ONLY":
        raise TrendSwingError("unexpected TS-1A stage")
    _require_false(
        document,
        (
            "read_post_entry_return",
            "read_mae_mfe",
            "model_training",
            "model_prediction",
            "strategy_backtest",
            "candidate_effect_evaluation",
            "paper_account",
            "production_change",
            "web_implementation",
            "external_network",
        ),
    )
    scope = document.get("scope", {})
    if scope.get("universe_id") != "csi800-pit-v1" or scope.get("bse_included") is not False:
        raise TrendSwingError("TS-1A universe contract differs")
    market = document.get("market_and_sector", {})
    mapping = market.get("listing_segment_mapping", {})
    expected = {"main": "000906.SH", "chinext": "399006.SZ", "star": "000688.SH"}
    actual = {key: value.get("benchmark_code") for key, value in mapping.items()}
    if actual != expected or any(value.get("fallback_allowed") is not False for value in mapping.values()):
        raise TrendSwingError("TS-1A segment benchmark contract differs")
    hotspot = market.get("hotspot_sector", {})
    if hotspot.get("taxonomy") != "SW_L1_PIT" or hotspot.get("weighting") != "equal_weight":
        raise TrendSwingError("TS-1A sector construction differs")
    if hotspot.get("official_index_claim_allowed") is not False:
        raise TrendSwingError("derived sector basket cannot claim official index authority")
    factor = document.get("alpha158", {})
    if factor.get("role") != "ranking_only" or factor.get("historical_backfill_with_current_model") != "forbidden":
        raise TrendSwingError("TS-1A Alpha158 boundary differs")
    changes = document.get("attempt_and_change_control", {})
    expected_controls = {
        "strategy_effect_attempt_count": 0,
        "data_profile_attempt_count": 1,
        "full_sample_threshold_optimization": "forbidden",
        "parameter_grid": "forbidden",
        "result_based_relaxation": "forbidden",
        "same_scope_rerun_after_semantic_read": "forbidden",
    }
    if any(changes.get(key) != value for key, value in expected_controls.items()):
        raise TrendSwingError("TS-1A attempt controls differ")


@dataclass(frozen=True)
class TrendSwingProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "TrendSwingProtocol":
        resolved = project_path(path)
        document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TrendSwingError("TS-1A protocol must be a mapping")
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))

    @property
    def start_date(self) -> str:
        return str(self.document["scope"]["start_date"]).replace("-", "")

    @property
    def end_date(self) -> str:
        return str(self.document["scope"]["end_date"]).replace("-", "")

    @property
    def required_sources(self) -> tuple[str, ...]:
        return tuple(self.document["data_gates"]["required_sources"])
