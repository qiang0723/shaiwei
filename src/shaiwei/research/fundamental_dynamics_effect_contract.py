"""Frozen result-before contract for the F2-1 historical effect gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.fundamental_effect.contract import CandidateSpec, FundamentalEffectError
from shaiwei.research.fundamental_effect.io import sha256_json
from shaiwei.research.fundamental_pit_recovery_contract import project_relative


PROTOCOL_SCHEMA = "f2-csi800-fundamental-effect-v1"
PROTOCOL_ID = "f2-csi800-fundamental-dynamics-effect-gate-v1"
PROTOCOL_SHA256 = "f186296c37a5e167591d2fd5ca802556c3d8e4993478f0f62724181ba2a4bdae"
RESEARCH_FAMILY = "f2-csi800-fundamental-dynamics-v1"
FEATURE_IDENTITY = (
    ("fundamental_asset_growth_v1", -1, 5, 5),
    ("fundamental_revenue_growth_v1", 1, 5, 5),
    ("fundamental_operating_profit_change_v1", 1, 9, 9),
    ("fundamental_net_income_change_v1", 1, 9, 9),
    ("fundamental_operating_cashflow_change_v1", 1, 9, 9),
    ("fundamental_cash_balance_change_v1", 1, 9, 9),
)


@dataclass(frozen=True)
class FundamentalDynamicsEffectProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    candidates: tuple[CandidateSpec, ...]

    @classmethod
    def load(cls, path: Path) -> "FundamentalDynamicsEffectProtocol":
        if not path.is_file():
            raise FundamentalEffectError("F2-1 protocol is missing")
        digest = sha256_file(path)
        if digest != PROTOCOL_SHA256:
            raise FundamentalEffectError("F2-1 protocol hash differs from the result-before freeze")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise FundamentalEffectError("F2-1 protocol must be a YAML object")
        cls._validate(document)
        candidates = tuple(
            CandidateSpec(
                name=str(item["candidate"]),
                formula=str(item["formula"]),
                direction=int(item["pre_registered_direction"]),
                rationale=str(item["rationale"]),
                expression_tokens=int(item["expression_tokens"]),
                ast_nodes=int(item["ast_nodes"]),
            )
            for item in document["candidate_policy"]
        )
        return cls(path=path, document=document, sha256=digest, candidates=candidates)

    @staticmethod
    def _validate(document: dict[str, Any]) -> None:
        if document.get("schema_version") != PROTOCOL_SCHEMA or document.get("protocol_id") != PROTOCOL_ID:
            raise FundamentalEffectError("F2-1 protocol identity differs")
        if document.get("effect_results_inspected_before_freeze") is not False:
            raise FundamentalEffectError("F2-1 result-before disclosure differs")
        _validate_scope(document.get("scope", {}))
        _validate_predecessor(document.get("predecessor", {}))
        _validate_candidates(document.get("candidate_policy", []))
        _validate_evaluation(document.get("evaluation", {}))
        _validate_multiple_testing(document.get("multiple_testing", {}))
        _validate_permissions(document.get("permissions", {}))
        terminal = document.get("terminal_policy", {})
        if terminal.get("stop_after_six_candidates") is not True:
            raise FundamentalEffectError("F2-1 stopping rule differs")

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


def _validate_scope(scope: dict[str, Any]) -> None:
    expected = {
        "universe_id": "csi800-pit-v1",
        "official_index_code": "000906.SH",
        "benchmark_qlib_code": "SH000906",
        "research_family": RESEARCH_FAMILY,
        "candidate_attempt_count": 6,
        "model_training_authorized": False,
        "historical_effect_authorized_after_protocol_push": True,
        "forward_signal_authorized": False,
        "paper_portfolio_authorized": False,
        "production_authorization": "none",
    }
    if scope != expected:
        raise FundamentalEffectError("F2-1 scope or authority differs")


def _validate_predecessor(predecessor: dict[str, Any]) -> None:
    tracked = project_relative(PROJECT_ROOT, str(predecessor.get("data_tracked_manifest", "")))
    effect = project_relative(PROJECT_ROOT, str(predecessor.get("related_effect_manifest", "")))
    if (
        predecessor.get("data_protocol_id")
        != "f2-csi800-fundamental-dynamics-recovery-data-feature-gate-v2"
        or predecessor.get("data_verdict")
        != "GO_F2_FUNDAMENTAL_DYNAMICS_RECOVERY_DATA_FEATURE_GATE_ONLY"
        or not tracked.is_file()
        or sha256_file(tracked) != predecessor.get("data_tracked_manifest_sha256")
        or predecessor.get("related_effect_protocol_id")
        != "f1-csi800-fundamental-effect-gate-v1"
        or predecessor.get("related_effect_verdict") != "REJECT"
        or predecessor.get("related_effect_attempt_count") != 6
        or not effect.is_file()
        or sha256_file(effect) != predecessor.get("related_effect_manifest_sha256")
        or predecessor.get("preserve_without_rewrite") is not True
    ):
        raise FundamentalEffectError("F2-1 predecessor identity differs")
    data_manifest = json.loads(tracked.read_text(encoding="utf-8"))
    effect_manifest = json.loads(effect.read_text(encoding="utf-8"))
    if data_manifest.get("verdict") != predecessor["data_verdict"] or (
        effect_manifest.get("verdict") != "REJECT"
        or effect_manifest.get("candidate_attempt_count") != 6
        or effect_manifest.get("formal_library_insertions") != 0
    ):
        raise FundamentalEffectError("F2-1 predecessor decision differs")


def _validate_candidates(items: list[dict[str, Any]]) -> None:
    actual = tuple(
        (
            str(item.get("candidate")),
            int(item.get("pre_registered_direction", 0)),
            int(item.get("expression_tokens", 0)),
            int(item.get("ast_nodes", 0)),
        )
        for item in items
    )
    if actual != FEATURE_IDENTITY or any(not str(item.get("rationale", "")).strip() for item in items):
        raise FundamentalEffectError("F2-1 candidate identity differs")


def _validate_evaluation(evaluation: dict[str, Any]) -> None:
    if (
        evaluation.get("discovery")
        != {
            "start": "2016-07-01",
            "end": "2018-12-31",
            "minimum_daily_rank_ic_observations": 252,
        }
        or evaluation.get("oos_windows") != ["W1", "W2", "W3", "W4", "W5", "W6"]
        or evaluation.get("g1_spec") != "g1-v1"
        or evaluation.get("formal_library_insertions") != 0
    ):
        raise FundamentalEffectError("F2-1 evaluation windows or G1 spec differs")


def _validate_multiple_testing(value: dict[str, Any]) -> None:
    if (
        value.get("current_candidate_attempt_count") != 6
        or value.get("related_predecessor_attempt_count") != 6
        or value.get("related_trial_families")
        != ["f1-csi800-fundamental-v1", RESEARCH_FAMILY]
        or value.get("cumulative_trial_count_after_complete_run") != 12
        or value.get("no_unregistered_variants") is not True
    ):
        raise FundamentalEffectError("F2-1 multiple-testing contract differs")


def _validate_permissions(permissions: dict[str, Any]) -> None:
    if (
        permissions.get("network") is not False
        or permissions.get("env_read") is not False
        or permissions.get("tushare_calls") != 0
        or permissions.get("deepseek_calls") != 0
        or permissions.get("scheduler_change_or_restart") is not False
        or permissions.get("csi800_production_change") is not False
    ):
        raise FundamentalEffectError("F2-1 must remain offline and production-isolated")
