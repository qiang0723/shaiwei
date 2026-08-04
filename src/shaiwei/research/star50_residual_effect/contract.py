"""Frozen M4-1 protocol, release, and immutable-input contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import pyarrow.parquet as pq
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head


PROTOCOL_PATH = PROJECT_ROOT / "config/m4_star50_residual_effect_v1.yaml"


class ResidualEffectError(RuntimeError):
    """Fail-closed M4-1 contract or execution violation."""


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


def project_path(value: str, *, project_root: Path = PROJECT_ROOT) -> Path:
    path = (project_root / value).resolve()
    if not path.is_relative_to(project_root.resolve()):
        raise ResidualEffectError("M4-1 path escapes the project root")
    return path


def _validate(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "m4-star50-benchmark-residual-effect-v1":
        raise ResidualEffectError("unexpected M4-1 protocol identity")
    if document.get("production_authorization") != "none":
        raise ResidualEffectError("M4-1 cannot authorize production")
    scope = document.get("scope", {})
    forbidden_true = (
        "candidate_formula_or_direction_change_authorized",
        "model_training_authorized",
        "deepseek_or_external_api_authorized",
        "production_signal_or_paper_portfolio_authorized",
        "scheduler_web_or_production_changes",
    )
    if any(scope.get(name) is not False for name in forbidden_true):
        raise ResidualEffectError("M4-1 scope was broadened")
    expected = {
        "residual_momentum_35_skip5",
        "residual_reversal_5",
        "negative_idiosyncratic_volatility_40",
    }
    candidates = document.get("candidates", [])
    if len(candidates) != 3 or {row.get("candidate_id") for row in candidates} != expected:
        raise ResidualEffectError("M4-1 fixed candidate set differs")
    if any(int(row.get("orientation", 0)) != 1 for row in candidates):
        raise ResidualEffectError("M4-1 fixed candidate direction differs")
    evaluation = document.get("evaluation", {})
    if evaluation.get("formal_g1_v1_status") != "NOT_RUN_UNIVERSE_WINDOW_DOMAIN_MISMATCH":
        raise ResidualEffectError("M4-1 must not impersonate formal G1-v1")
    if len(evaluation.get("oos_windows", [])) != 6:
        raise ResidualEffectError("M4-1 requires exactly six frozen OOS windows")
    if len(evaluation.get("pressure_periods", [])) != 3:
        raise ResidualEffectError("M4-1 requires exactly three frozen pressure periods")
    if document.get("research_multiplicity", {}).get("related_price_volume_attempt_background") != 273:
        raise ResidualEffectError("M4-1 global multiplicity background differs")


@dataclass(frozen=True)
class EffectProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "EffectProtocol":
        path = path.resolve()
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ResidualEffectError("M4-1 protocol is not a mapping")
        _validate(document)
        return cls(path=path, document=document, sha256=sha256_file(path))

    def verify_upstream(self, *, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
        upstream = self.document["upstream_contract"]
        evidence: dict[str, Any] = {}
        for key, value in upstream.items():
            if not key.endswith("_path"):
                continue
            hash_key = f"{key[:-5]}_sha256"
            if hash_key not in upstream:
                continue
            path = project_path(str(value), project_root=project_root)
            if not path.is_file() or sha256_file(path) != str(upstream[hash_key]):
                raise ResidualEffectError(f"M4-1 upstream hash mismatch: {key}")
            evidence[key[:-5]] = {"path": str(value), "sha256": str(upstream[hash_key])}
        predictions = upstream.get("corrected_prediction_inputs", [])
        if len(predictions) != 6:
            raise ResidualEffectError("M4-1 prediction input count differs")
        for row in predictions:
            path = project_path(str(row["path"]), project_root=project_root)
            if not path.is_file() or sha256_file(path) != str(row["sha256"]):
                raise ResidualEffectError(f"M4-1 prediction hash mismatch: {row['purpose']}")
            if pq.read_metadata(path).num_rows != int(row["rows"]):
                raise ResidualEffectError(f"M4-1 prediction row count mismatch: {row['purpose']}")
        m4_manifest = json.loads(
            project_path(upstream["m4_data_manifest_path"], project_root=project_root).read_text()
        )
        if m4_manifest.get("verdict") != "GO_M4_STAR50_RESIDUAL_DATA_PREEXECUTION_ONLY":
            raise ResidualEffectError("M4-0 data gate is not GO")
        if m4_manifest.get("strategy_results_inspected") is not False:
            raise ResidualEffectError("M4-0 result-blind status differs")
        return evidence


@dataclass(frozen=True)
class EffectRelease:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: EffectProtocol,
        *,
        code_bundle_sha256: str,
    ) -> "EffectRelease":
        path = path.resolve()
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        expected = {
            "protocol_sha256": protocol.sha256,
            "code_bundle_sha256": code_bundle_sha256,
            "execution_authorized": True,
            "label_and_sealed_oos_read_authorized": True,
            "model_training_authorized": False,
            "provider_calls_authorized": False,
            "api_key_read_authorized": False,
            "production_authorization": "none",
        }
        if not isinstance(document, dict) or any(document.get(k) != v for k, v in expected.items()):
            raise ResidualEffectError("M4-1 execution release differs")
        implementation_head = str(document.get("implementation_git_head", ""))
        if len(implementation_head) != 40:
            raise ResidualEffectError("M4-1 implementation commit is not bound")
        return cls(path=path, document=document, sha256=sha256_file(path))


def verify_pushed_clean_state(release: EffectRelease, *, project_root: Path = PROJECT_ROOT) -> str:
    if os.getenv("SHAIWEI_RELEASE_MANIFEST"):
        code_snapshot_sha256()
        embedded_head = git_head()
        if embedded_head != str(release.document["implementation_git_head"]):
            raise ResidualEffectError("M4-1 image Git identity differs from implementation release")
        return embedded_head

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    if git("status", "--porcelain", "--untracked-files=no"):
        raise ResidualEffectError("M4-1 tracked worktree is not clean")
    head = git("rev-parse", "HEAD")
    if head != git("rev-parse", "origin/main"):
        raise ResidualEffectError("M4-1 HEAD is not pushed to origin/main")
    implementation = str(release.document["implementation_git_head"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, head],
        cwd=project_root,
        check=False,
    )
    if ancestor.returncode != 0:
        raise ResidualEffectError("M4-1 implementation commit is not an ancestor of release HEAD")
    return head
