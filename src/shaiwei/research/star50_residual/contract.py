"""Frozen contracts and immutable input checks for M4-0."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT


PROTOCOL_PATH = PROJECT_ROOT / "config/m4_star50_residual_factor_v1.yaml"


class ResidualGateError(ValueError):
    """Fail-closed M4-0 protocol, input, or output violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_document(document: dict[str, Any]) -> None:
    scope = document.get("scope", {})
    if document.get("protocol_id") != "m4-star50-benchmark-residual-v1":
        raise ResidualGateError("unexpected M4-0 protocol identity")
    if document.get("production_authorization") != "none":
        raise ResidualGateError("M4-0 cannot authorize production")
    forbidden_truths = (
        "factor_effect_or_rank_ic_authorized",
        "label_read_authorized",
        "sealed_validation_read_authorized",
        "llm_or_external_api_authorized",
        "model_backtest_portfolio_signal_authorized",
        "scheduler_or_web_changes",
    )
    if any(scope.get(field) is not False for field in forbidden_truths):
        raise ResidualGateError("M4-0 result-blind scope was broadened")
    candidates = document.get("candidates", [])
    expected = {
        "residual_momentum_35_skip5",
        "residual_reversal_5",
        "negative_idiosyncratic_volatility_40",
    }
    if {row.get("candidate_id") for row in candidates} != expected or len(candidates) != 3:
        raise ResidualGateError("M4-0 fixed candidate set differs")
    if document.get("data_clock", {}).get("bse_suffix_forbidden") != ".BJ":
        raise ResidualGateError("M4-0 must forbid .BJ")


@dataclass(frozen=True)
class ResidualProtocol:
    """Loaded immutable M4-0 protocol."""

    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "ResidualProtocol":
        path = path.resolve()
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ResidualGateError("M4-0 protocol is not a mapping")
        _validate_document(document)
        return cls(path=path, document=document, sha256=sha256_file(path))

    def path_for(self, field: str, *, project_root: Path = PROJECT_ROOT) -> Path:
        relative = self.document["upstream_contract"][field]
        path = (project_root / relative).resolve()
        try:
            path.relative_to(project_root.resolve())
        except ValueError as error:
            raise ResidualGateError(f"M4-0 path escapes project root: {field}") from error
        return path

    def verify_upstream(self, *, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
        upstream = self.document["upstream_contract"]
        bindings = {
            "registry": ("registry_path", "registry_sha256"),
            "p2_engineering_manifest": (
                "p2_engineering_manifest_path",
                "p2_engineering_manifest_sha256",
            ),
            "official_member_days": ("official_member_days_path", "official_member_days_sha256"),
            "market": ("market_path", "market_sha256"),
            "benchmark": ("benchmark_path", "benchmark_sha256"),
        }
        evidence: dict[str, Any] = {}
        for name, (path_field, hash_field) in bindings.items():
            path = self.path_for(path_field, project_root=project_root)
            if not path.is_file():
                raise ResidualGateError(f"missing M4-0 upstream artifact: {name}")
            actual = sha256_file(path)
            if actual != upstream[hash_field]:
                raise ResidualGateError(f"M4-0 upstream hash mismatch: {name}")
            evidence[name] = {"path": upstream[path_field], "sha256": actual}

        registry = yaml.safe_load(self.path_for("registry_path", project_root=project_root).read_text())
        universe = next(
            (
                row
                for row in registry.get("universes", [])
                if row.get("universe_id") == self.document["identity"]["universe_id"]
            ),
            None,
        )
        permission = upstream["required_universe_permission"]
        if universe is None or universe.get("pit_status") != "READY":
            raise ResidualGateError("STAR50 PIT universe is not READY")
        if permission not in universe.get("permissions", []):
            raise ResidualGateError("STAR50 factor protocol permission is absent")

        p2_manifest = json.loads(
            self.path_for("p2_engineering_manifest_path", project_root=project_root).read_text()
        )
        if p2_manifest.get("verdict") != "GO" or p2_manifest.get("strategy_results_inspected") is not False:
            raise ResidualGateError("P2-1 engineering evidence is not reusable result-blind truth")
        return evidence


@dataclass(frozen=True)
class ResidualExecutionRelease:
    """One-off release binding for the first real M4-0 feature construction."""

    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: ResidualProtocol,
        *,
        code_bundle_sha256: str,
    ) -> "ResidualExecutionRelease":
        path = path.resolve()
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ResidualGateError("M4-0 execution release is not a mapping")
        expected = {
            "protocol_sha256": protocol.sha256,
            "code_bundle_sha256": code_bundle_sha256,
            "execution_authorized": True,
            "provider_calls_authorized": False,
            "api_key_read_authorized": False,
            "production_authorization": "none",
        }
        mismatches = {key for key, value in expected.items() if document.get(key) != value}
        if mismatches:
            raise ResidualGateError(f"M4-0 execution release mismatch: {sorted(mismatches)}")
        return cls(path=path, document=document, sha256=sha256_file(path))

