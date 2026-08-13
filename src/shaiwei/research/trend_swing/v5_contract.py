"""Pinned TS-v5 governance and prompt bundle loader."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.v5_models import Mechanism, candidate_schema

GOVERNANCE_PATH = PROJECT_ROOT / "config/ts_v5_evolutionary_research_v1.yaml"
PROMPT_PATH = PROJECT_ROOT / "config/ts_v5_llm_prompt_v1.yaml"
GOVERNANCE_SHA256 = "52ea721b5b9711dc9f0637e9230d9b934a3b075e2e5203d600d119cfb30c335b"
PROMPT_SHA256 = "bf046a1072e64346c14595d13b0d3f5cdee838df3a631dc7f4f85a92798e5e89"


class V5ContractError(RuntimeError):
    """TS-v5 governance or prompt material is missing or has drifted."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path, expected_sha: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(PROJECT_ROOT.resolve(strict=True))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise V5ContractError("TS-v5 contract path is missing or outside the project") from exc
    if path.is_symlink() or not resolved.is_file() or sha256_file(resolved) != expected_sha:
        raise V5ContractError("TS-v5 contract identity mismatch")
    try:
        value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise V5ContractError("TS-v5 contract cannot be parsed") from exc
    if not isinstance(value, dict):
        raise V5ContractError("TS-v5 contract must be an object")
    return value


@dataclass(frozen=True)
class V5Bundle:
    governance: dict[str, Any]
    prompt: dict[str, Any]

    @classmethod
    def load(cls) -> "V5Bundle":
        governance = _load_yaml(GOVERNANCE_PATH, GOVERNANCE_SHA256)
        prompt = _load_yaml(PROMPT_PATH, PROMPT_SHA256)
        expected_mechanisms = [item.value for item in Mechanism]
        if (
            governance.get("schema_version") != "ts-v5-evolutionary-research-v1"
            or governance.get("status")
            != "FROZEN_GOVERNANCE_ENGINEERING_AUTHORIZED_LIVE_RESEARCH_NOT_AUTHORIZED"
            or governance.get("mechanism_archetypes") != expected_mechanisms
            or governance.get("llm_boundary", {}).get("live_call_authorized") is not False
            or governance.get("current_authority", {}).get("real_market_or_effect_read") is not False
        ):
            raise V5ContractError("TS-v5 governance authority has broadened")
        schedule = prompt.get("attempt_schedule", {})
        if (
            prompt.get("schema_version") != "ts-v5-llm-prompt-v1"
            or prompt.get("governance_config_sha256") != GOVERNANCE_SHA256
            or schedule.get("order") != expected_mechanisms
            or schedule.get("independent_attempts") != 6
            or schedule.get("adversarial_revisions") != 6
            or schedule.get("total_completed_responses_exact") != 12
        ):
            raise V5ContractError("TS-v5 prompt schedule differs from governance")
        schema = candidate_schema()
        if schema.get("additionalProperties") is not False:
            raise V5ContractError("TS-v5 candidate schema must reject extra fields")
        return cls(governance=governance, prompt=prompt)

    @property
    def system_prompt(self) -> str:
        value = self.prompt.get("system_prompt")
        if not isinstance(value, str) or not value.strip():
            raise V5ContractError("TS-v5 system prompt is missing")
        return value

    @property
    def mechanisms(self) -> tuple[Mechanism, ...]:
        return tuple(Mechanism(item) for item in self.governance["mechanism_archetypes"])

    def identity(self) -> dict[str, str]:
        return {
            "governance_sha256": GOVERNANCE_SHA256,
            "prompt_sha256": PROMPT_SHA256,
            "candidate_schema_sha256": sha256_text(canonical_json(candidate_schema())),
        }
