"""Frozen zero-provider-call recovery contract for the M1-1 terminal assembler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError


RECOVERY_CONFIG_SHA256 = "5f61141d2aed7f0404ce01f728d9d5838d3298e1a6244fc7a2c72cf34ddbd428"


@dataclass(frozen=True)
class M1Star50TerminalRecovery:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path) -> "M1Star50TerminalRecovery":
        if not path.is_file() or sha256_file(path) != RECOVERY_CONFIG_SHA256:
            raise D1ControlError("M1-1 terminal recovery config differs from its freeze")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise D1ControlError("M1-1 terminal recovery config is invalid") from error
        if not isinstance(document, dict):
            raise D1ControlError("M1-1 terminal recovery config must be an object")
        if (
            document.get("schema_version") != "m1-star50-factor-terminal-recovery-v1"
            or document.get("recovery_id")
            != "m1-star50-price-volume-v1-terminal-recovery-001"
            or document.get("status")
            != "M1_1_POST_RESPONSE_TERMINAL_ASSEMBLER_RECOVERY_FROZEN"
            or document.get("api_calls_authorized") is not False
            or int(document.get("additional_completed_responses_authorized", -1)) != 0
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M1-1 terminal recovery authority differs")
        return cls(path=path, document=document, sha256=sha256_file(path))

    @property
    def original_code_snapshot_sha256(self) -> str:
        return str(self.document["frozen_parent"]["code_snapshot_sha256"])

    @property
    def original_release_git_head(self) -> str:
        return str(self.document["frozen_parent"]["release_git_head"])

    def verify_frozen_evidence(
        self,
        *,
        project_root: Path,
        static_evidence: dict[str, int],
        report_path: Path,
    ) -> None:
        if report_path.exists():
            raise D1ControlError("M1-1 recovery may only assemble an absent terminal report")
        expected_static = {
            "attempt_rows": 40,
            "discovery_artifacts": 14,
            "raw_response_artifacts": 40,
            "transport_completions": 40,
            "transport_events": 80,
        }
        if static_evidence != expected_static:
            raise D1ControlError("M1-1 recovery static evidence differs from the freeze")
        evidence = self.document["immutable_completed_evidence"]
        paths = {
            "attempt_ledger_sha256": "ledger/m1_star50_factor_attempts.csv",
            "transport_ledger_sha256": "ledger/m1_star50_factor_transports.csv",
            "experiment_ledger_sha256": "ledger/experiments.csv",
        }
        old = self.document["old_d1_immutable_evidence"]
        paths.update(
            {
                "llm_factor_attempts_sha256": "ledger/llm_factor_attempts.csv",
                "llm_factor_attempts_v2_sha256": "ledger/llm_factor_attempts_v2.csv",
                "llm_factor_transports_sha256": "ledger/llm_factor_transports.csv",
                "llm_factor_transports_v2_sha256": "ledger/llm_factor_transports_v2.csv",
                "factor_admissions_sha256": "ledger/factor_admissions.csv",
            }
        )
        for key, relative in paths.items():
            expected = evidence.get(key, old.get(key))
            if sha256_file(project_root / relative) != expected:
                raise D1ControlError(f"M1-1 recovery evidence differs: {relative}")
