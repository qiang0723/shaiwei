"""Frozen R2-1R1 contract: pinned protocol, account identities, reset rules and the latching gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import sha256_file


class R21R1Error(RuntimeError):
    """Evidence integrity failure: the checkpoint is BLOCKED_EVIDENCE, never silently reclassified as a gap."""


PROTOCOL_RELATIVE = "config/r2_1r1_continuous_segment_checkpoint_v1.yaml"
PROTOCOL_SHA256 = "d7c483470ac25757c8d3111cfc3e64e0ff6da1c67f1ce3c3ae71f619beea76a4"
DOCUMENT_RELATIVE = "docs/R2_1R1_CONTINUOUS_SEGMENT_CHECKPOINT_PROTOCOL_20261029.md"
DOCUMENT_SHA256 = "7542ec67483008d90568e29a8bf90042276e5909a41b671fe72feec57b24abcd"
REPORT_ROOT = PROJECT_ROOT / "data/research/r2-1r1"
TIMEZONE = ZoneInfo("Asia/Shanghai")
RESET_RULES = (
    "official_open_day_not_live_dual",
    "account_policy_sha256_change",
    "code_snapshot_sha256_differs_from_previous_live_dual_day",
)


@dataclass(frozen=True)
class Account:
    role: str
    account_id: str
    policy_version: str
    policy_sha256: str


@dataclass(frozen=True)
class Contract:
    document: dict[str, Any]
    control: Account
    comparison: Account
    sha256: str = PROTOCOL_SHA256

    @property
    def accounts(self) -> tuple[Account, Account]:
        return self.control, self.comparison

    @property
    def history_start(self) -> str:
        return str(self.document["history_start_execution_date"])

    @property
    def minimum_days(self) -> int:
        return int(self.document["gate"]["minimum_segment_live_dual_days"])

    @property
    def minimum_rebalances(self) -> int:
        return int(self.document["gate"]["minimum_segment_rebalance_cycles"])

    @classmethod
    def load(cls, root: Path = PROJECT_ROOT) -> "Contract":
        for relative, expected in ((PROTOCOL_RELATIVE, PROTOCOL_SHA256), (DOCUMENT_RELATIVE, DOCUMENT_SHA256)):
            path = root / relative
            if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
                raise R21R1Error(f"R2-1R1 frozen file differs: {relative}")
        try:
            document = yaml.safe_load((root / PROTOCOL_RELATIVE).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise R21R1Error("R2-1R1 protocol YAML is invalid") from exc
        if not isinstance(document, dict):
            raise R21R1Error("R2-1R1 protocol YAML is not a mapping")
        _check(document)
        accounts = document["accounts"]
        return cls(document, _account("control", accounts["control"]), _account("comparison", accounts["comparison"]))


def _account(role: str, row: Mapping[str, Any]) -> Account:
    return Account(role, str(row["account_id"]), str(row["execution_policy_version"]), str(row["policy_sha256"]))


def _check(document: Mapping[str, Any]) -> None:
    authority, gate = document.get("authority", {}), document.get("gate", {})
    segment, evaluator = document.get("segment", {}), document.get("evaluator", {})
    required = {
        "protocol": document.get("protocol_id") == "r2-1r1-continuous-segment-checkpoint-v1",
        "status": document.get("status") == "FROZEN_DESCRIPTIVE_ONLY",
        "predecessor kept": document.get("predecessor", {}).get("terminal_state_preserved") == "BLOCKED_EVIDENCE",
        "no effect gate": authority.get("strategy_effect_gate") == "NOT_DEFINED",
        "no production switch": authority.get("production_switch_authorized") is False,
        "gate": gate.get("minimum_segment_live_dual_days") == 20 and gate.get("minimum_segment_rebalance_cycles") == 2,
        "latch": gate.get("latch_on_first_reach") is True and gate.get("later_gaps_revoke_latch") is False,
        "reset rules": tuple(segment.get("reset_on", ())) == RESET_RULES,
        "gaps reset": segment.get("gap_is_blocking") is False,
        "web unchanged": evaluator.get("web_changes") == "none",
        "report go-ahead": evaluator.get("descriptive_report_run_requires_user_go_ahead") is True,
        "no nav before latch": "nav_or_return_values_before_latch" in document.get("prohibited_outputs", ()),
    }
    if failed := [name for name, ok in required.items() if not ok]:
        raise R21R1Error(f"R2-1R1 protocol authority or contract differs: {failed}")
