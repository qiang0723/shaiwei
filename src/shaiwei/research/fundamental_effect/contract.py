"""Frozen protocol and input identity checks for F1-1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import ingest_snapshot_sha256, sha256_file
from shaiwei.research.fundamental_effect.io import sha256_json
from shaiwei.research.fundamental_pit_contract import verify_source_evidence
from shaiwei.research.fundamental_pit_recovery_contract import project_relative
from shaiwei.transform.qlib_bin import qlib_tree_integrity


PROTOCOL_SCHEMA = "f1-csi800-fundamental-effect-v1"
PROTOCOL_ID = "f1-csi800-fundamental-effect-gate-v1"
PROTOCOL_SHA256 = "3062bcc629283a49a76cf4103a676c7f94c273e83aead1e89847a3d616544c3f"
RESEARCH_FAMILY = "f1-csi800-fundamental-v1"


class FundamentalEffectError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    formula: str
    direction: int
    rationale: str
    expression_tokens: int
    ast_nodes: int


COMPLEXITY = {
    "fundamental_net_income_to_assets_v2": (3, 3),
    "fundamental_operating_margin_v2": (3, 3),
    "fundamental_cash_return_on_assets_v2": (3, 3),
    "fundamental_leverage_v2": (3, 3),
    "fundamental_cash_to_assets_v2": (3, 3),
    "fundamental_accruals_to_assets_v2": (5, 5),
}


@dataclass(frozen=True)
class FundamentalEffectProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    candidates: tuple[CandidateSpec, ...]

    @classmethod
    def load(cls, path: Path) -> "FundamentalEffectProtocol":
        if not path.is_file():
            raise FundamentalEffectError("F1-1 protocol is missing")
        digest = sha256_file(path)
        if digest != PROTOCOL_SHA256:
            raise FundamentalEffectError("F1-1 protocol hash differs from the result-before freeze")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise FundamentalEffectError("F1-1 protocol must be a YAML object")
        cls._validate(document)
        candidates = tuple(
            CandidateSpec(
                name=str(item["candidate"]),
                formula=str(item["formula"]),
                direction=int(item["pre_registered_direction"]),
                rationale=str(item["rationale"]),
                expression_tokens=COMPLEXITY[str(item["candidate"])][0],
                ast_nodes=COMPLEXITY[str(item["candidate"])][1],
            )
            for item in document["candidate_policy"]
        )
        return cls(path=path, document=document, sha256=digest, candidates=candidates)

    @staticmethod
    def _validate(document: dict[str, Any]) -> None:
        if document.get("schema_version") != PROTOCOL_SCHEMA or document.get("protocol_id") != PROTOCOL_ID:
            raise FundamentalEffectError("F1-1 protocol identity differs")
        scope = document.get("scope", {})
        if (
            scope.get("universe_id") != "csi800-pit-v1"
            or scope.get("research_family") != RESEARCH_FAMILY
            or scope.get("candidate_attempt_count") != 6
            or scope.get("model_training_authorized") is not False
            or scope.get("production_authorization") != "none"
        ):
            raise FundamentalEffectError("F1-1 authority or candidate budget differs")
        candidate_policy = document.get("candidate_policy", ())
        names = tuple(str(item.get("candidate")) for item in candidate_policy)
        if names != tuple(COMPLEXITY) or any(
            int(item.get("pre_registered_direction", 0)) not in {-1, 1}
            for item in candidate_policy
        ):
            raise FundamentalEffectError("F1-1 candidate order or direction differs")
        evaluation = document.get("evaluation", {})
        if (
            evaluation.get("discovery")
            != {
                "start": "2016-07-01",
                "end": "2018-12-31",
                "minimum_daily_rank_ic_observations": 252,
            }
            or evaluation.get("oos_windows") != ["W1", "W2", "W3", "W4", "W5", "W6"]
            or evaluation.get("g1_spec") != "g1-v1"
        ):
            raise FundamentalEffectError("F1-1 evaluation windows or G1 spec differs")
        permissions = document.get("permissions", {})
        if (
            permissions.get("network") is not False
            or permissions.get("env_read") is not False
            or permissions.get("tushare_calls") != 0
            or permissions.get("deepseek_calls") != 0
            or permissions.get("scheduler_change_or_restart") is not False
        ):
            raise FundamentalEffectError("F1-1 must remain offline and production-isolated")
        if document.get("terminal_policy", {}).get("stop_after_six_candidates") is not True:
            raise FundamentalEffectError("F1-1 stopping rule differs")

    @property
    def required_apis(self) -> tuple[str, ...]:
        return tuple(
            str(value)
            for value in self.document["input_bindings"]["exposure_source_snapshot"][
                "required_apis"
            ]
        )

    def project_path(self, value: str, *, project_root: Path = PROJECT_ROOT) -> Path:
        return project_relative(project_root, value)

    @property
    def output_root(self) -> Path:
        return self.project_path(str(self.document["outputs"]["ignored_root"]))

    @property
    def policy_sha256(self) -> str:
        return sha256_json(
            {
                "candidate_policy": self.document["candidate_policy"],
                "feature_timing": self.document["feature_timing"],
                "residualization": self.document["residualization"],
                "evaluation": self.document["evaluation"],
                "multiple_testing": self.document["multiple_testing"],
                "terminal_policy": self.document["terminal_policy"],
            }
        )


def _verify_file_binding(
    protocol: FundamentalEffectProtocol,
    binding: dict[str, Any],
    *,
    project_root: Path,
) -> dict[str, object]:
    path = protocol.project_path(str(binding["path"]), project_root=project_root)
    expected = str(binding["sha256"])
    if not path.is_file() or sha256_file(path) != expected:
        raise FundamentalEffectError(f"F1-1 bound input differs: {path.name}")
    result: dict[str, object] = {
        "path": path.relative_to(project_root).as_posix(),
        "sha256": expected,
    }
    if "row_count" in binding:
        actual_rows = pq.read_metadata(path).num_rows
        if actual_rows != int(binding["row_count"]):
            raise FundamentalEffectError(f"F1-1 bound row count differs: {path.name}")
        result["row_count"] = actual_rows
    return result


def verify_inputs(
    protocol: FundamentalEffectProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    bindings = protocol.document["input_bindings"]
    files = {
        name: _verify_file_binding(protocol, bindings[name], project_root=project_root)
        for name in (
            "fundamental_feature_panel",
            "fundamental_quality_report",
            "fundamental_manifest",
            "alpha158_predictions",
        )
    }
    qlib = bindings["qlib_provider"]
    manifest_path = protocol.project_path(str(qlib["manifest_path"]), project_root=project_root)
    if not manifest_path.is_file() or sha256_file(manifest_path) != str(qlib["manifest_sha256"]):
        raise FundamentalEffectError("F1-1 qlib manifest differs")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FundamentalEffectError("F1-1 qlib manifest is invalid") from error
    expected_qlib = {
        "artifact_sha256": str(qlib["tree_sha256"]),
        "artifact_file_count": int(qlib["file_count"]),
        "artifact_byte_count": int(qlib["byte_count"]),
    }
    if any(manifest.get(key) != value for key, value in expected_qlib.items()):
        raise FundamentalEffectError("F1-1 qlib tree identity differs")
    qlib_root = protocol.project_path(str(qlib["path"]), project_root=project_root)
    actual_qlib = qlib_tree_integrity(qlib_root)
    if actual_qlib != expected_qlib:
        raise FundamentalEffectError("F1-1 qlib content failed a full tree rehash")
    expected_ingest = str(bindings["exposure_source_snapshot"]["ingest_snapshot_sha256"])
    actual_ingest = ingest_snapshot_sha256()
    if actual_ingest != expected_ingest:
        raise FundamentalEffectError("F1-1 ingest snapshot changed after protocol freeze")
    sources = verify_source_evidence(protocol)
    return {
        "protocol_sha256": protocol.sha256,
        "policy_sha256": protocol.policy_sha256,
        "files": files,
        "qlib": {
            "manifest_path": manifest_path.relative_to(project_root).as_posix(),
            "manifest_sha256": str(qlib["manifest_sha256"]),
            **actual_qlib,
        },
        "ingest_snapshot_sha256": actual_ingest,
        "sources": sources,
        "input_snapshot_sha256": sha256_json(
            {
                "protocol_sha256": protocol.sha256,
                "files": files,
                "qlib": expected_qlib,
                "ingest_snapshot_sha256": actual_ingest,
                "sources": sources,
            }
        ),
    }
