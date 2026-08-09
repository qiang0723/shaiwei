"""Frozen identities and authority for M7 evidence-recovery engineering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.research_gates.m7_moneyflow.contract import sha256_file


PROTOCOL_ID = "m7-moneyflow-evidence-recovery-v1"
PROTOCOL_SHA256 = "93a774d8939d443dd5d925e61a7f4727ff9464a969171dcaca58322f9b2b5d53"
ENGINEERING_ID = "m7-moneyflow-evidence-recovery-engineering-v1"
ENGINEERING_SHA256 = "873491b0f3b6b908e4a54c4579c35def3c322ce9adbe033f4f20fdf194a106dd"
UNIVERSE_IDS = (
    "star-board-all-pit-v1",
    "star-board-midcap-pit-v1",
    "star-board-smallcap-pit-v1",
)
TARGET_COLUMNS = ("trade_date", "universe_id", "ts_code", "segment")


class RecoveryError(RuntimeError):
    """A frozen recovery identity, input, or quality invariant failed."""


def _mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoveryError(f"{path.name} must contain a mapping")
    return value


def _bound_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise RecoveryError("recovery frozen files cannot be symlinks")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise RecoveryError("recovery frozen file is missing or outside project root") from error
    if not resolved.is_file():
        raise RecoveryError("recovery frozen input is not a regular file")
    return resolved


@dataclass(frozen=True)
class RecoveryProtocol:
    project_root: Path
    document: dict[str, Any]
    engineering: dict[str, Any]
    sha256: str
    engineering_sha256: str

    @classmethod
    def load(
        cls,
        protocol_path: Path,
        *,
        engineering_path: Path,
        project_root: Path,
    ) -> RecoveryProtocol:
        document = _mapping(protocol_path)
        engineering = _mapping(engineering_path)
        physical = sha256_file(protocol_path)
        engineering_physical = sha256_file(engineering_path)
        if physical != PROTOCOL_SHA256 or document.get("protocol_id") != PROTOCOL_ID:
            raise RecoveryError("recovery protocol identity differs")
        if document.get("stage") != "RESULT_KNOWN_DUAL_TRACK_RECOVERY_PROTOCOL_ONLY":
            raise RecoveryError("recovery protocol stage differs")
        if (
            engineering_physical != ENGINEERING_SHA256
            or engineering.get("build_protocol_id") != ENGINEERING_ID
            or engineering.get("stage") != "SYNTHETIC_ENGINEERING_ONLY"
        ):
            raise RecoveryError("recovery engineering contract identity differs")
        predecessor = engineering.get("frozen_predecessor") or {}
        if (
            predecessor.get("protocol_sha256") != physical
            or predecessor.get("protocol_commit_pushed_before_engineering") is not True
            or predecessor.get("predecessor_scopes_closed") is not True
        ):
            raise RecoveryError("recovery engineering predecessor differs")
        for field in ("execution_manifest_path", "execution_acceptance_path"):
            frozen = _bound_file(project_root, str(document["predecessor"][field]))
            if sha256_file(frozen) != document["predecessor"][field.replace("path", "sha256")]:
                raise RecoveryError("recovery lineage evidence differs")
        authority = engineering.get("authority") or {}
        forbidden = (
            "exact_release_scope_generation_authorized",
            "real_security_key_read_authorized",
            "moneyflow_numeric_value_read_authorized",
            "tushare_or_baostock_live_call_authorized",
            "secret_read_authorized",
            "external_network_authorized",
            "actual_recovery_authorized",
            "adjusted_coverage_authorized",
            "candidate_generation_authorized",
            "label_return_model_backtest_authorized",
            "forward_paper_production_authorized",
            "scheduler_or_web_change_authorized",
        )
        if (
            authority.get("synthetic_engineering_authorized") is not True
            or any(authority.get(field) is not False for field in forbidden)
            or authority.get("production_authorization") != "none"
            or authority.get("research_attempt_increment") != 0
        ):
            raise RecoveryError("recovery engineering contract expands authority")
        if tuple(document["frozen_domain"]["universe_ids"]) != UNIVERSE_IDS:
            raise RecoveryError("recovery universe identities differ")
        return cls(project_root, document, engineering, physical, engineering_physical)

    @property
    def moneyflow_fields(self) -> tuple[str, ...]:
        return tuple(self.document["track_b_same_semantic_moneyflow"]["canonical_fields"])

    @property
    def expected_track_a_rows(self) -> int:
        return int(self.document["frozen_domain"]["track_a_expected_member_row_count"])

    @property
    def expected_track_b_rows(self) -> int:
        return int(self.document["frozen_domain"]["track_b_expected_member_row_count"])
