"""Fail-closed loading of the frozen M5 proposal authority bundle."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import FixedAuthority, canonical_json, sha256_text

CONFIG_RELATIVE_PATH = Path("config/m5_research_proposal_control_v2.yaml")
EXPECTED_CONFIG_SHA256 = "4113323415bcc512a6eeae6e3f00f823a114d63b604fdb16c85fe4aa94cd94c5"
CONSTITUTION_RELATIVE_PATH = Path("docs/ARCHITECTURE_CONSTITUTION.md")
CONSTITUTION_SHA256 = "d312dd6389dde45528e8360bbb213456bde8c2522f786892a599421821e1804e"
REGISTRY_RELATIVE_PATH = Path("config/m1_multi_universe_v1.yaml")


class AuthorityError(RuntimeError):
    """Frozen authority material is absent, invalid, or has drifted."""


@dataclass(frozen=True)
class MultiplicityScope:
    scope_id: str
    prior_attempt_count: int
    evidence_path: str
    evidence_sha256: str


@dataclass(frozen=True)
class FamilyRule:
    family_id: str
    hypothesis_id: str
    falsification_rule_id: str
    allowed_generation_modes: tuple[str, ...]
    primary: MultiplicityScope
    sensitivity: MultiplicityScope | None
    planned_increment_policy: str


@dataclass(frozen=True)
class AuthorityBundle:
    project_root: Path
    config: dict[str, Any]
    config_sha256: str
    authority_bundle_sha256: str
    snapshot_id: str
    snapshot_sha256: str
    eligible_universe_ids: tuple[str, ...]
    blocked_universe_ids: tuple[str, ...]
    families: dict[str, FamilyRule]
    fixed_authority: FixedAuthority

    @property
    def storage(self) -> dict[str, Any]:
        return self.config["storage"]

    @property
    def browser_security(self) -> dict[str, Any]:
        return self.config["browser_security"]

    @property
    def proposal_template(self) -> dict[str, Any]:
        return self.config["proposal_template"]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bound_path(root: Path, relative: str | Path) -> Path:
    candidate = root / Path(relative)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise AuthorityError(f"authority path is missing or escapes project root: {relative}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise AuthorityError(f"authority path must be a regular non-symlink file: {relative}")
    return resolved


def _verify_file(root: Path, relative: str | Path, expected_sha: str) -> Path:
    path = _bound_path(root, relative)
    if _file_sha256(path) != expected_sha:
        raise AuthorityError(f"authority SHA-256 mismatch: {relative}")
    return path


def _expect_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorityError(f"{name} must be an object")
    return value


def _load_config(root: Path) -> tuple[dict[str, Any], Path]:
    path = _verify_file(root, CONFIG_RELATIVE_PATH, EXPECTED_CONFIG_SHA256)
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AuthorityError("control config cannot be parsed") from exc
    config = _expect_dict(config, "config")
    if config.get("schema_version") != "m5-research-proposal-control-config-v2":
        raise AuthorityError("unknown control config schema")
    if config.get("config_id") != "m5-research-proposal-control-v2":
        raise AuthorityError("unexpected control config identity")
    return config, path


def _verify_snapshot(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    authority = _expect_dict(config.get("authority"), "authority")
    snapshot_id = authority.get("snapshot_id")
    relative = Path(str(authority.get("strategy_factory_root"))) / "snapshots" / f"{snapshot_id}.json"
    path = _verify_file(root, relative, str(authority.get("snapshot_sha256")))
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityError("strategy-factory snapshot cannot be parsed") from exc
    source = _expect_dict(snapshot.get("source_identity"), "snapshot source_identity")
    if snapshot.get("snapshot_id") != snapshot_id:
        raise AuthorityError("strategy-factory snapshot identity mismatch")
    if source.get("authority_addendum_sha256") != authority.get("authority_addendum_sha256"):
        raise AuthorityError("authority addendum identity mismatch")
    evidence = _expect_dict(source.get("evidence_hashes"), "snapshot evidence_hashes")
    if evidence.get(str(REGISTRY_RELATIVE_PATH)) != authority.get("universe_registry_sha256"):
        raise AuthorityError("universe registry identity mismatch")
    universe_rows = _expect_dict(snapshot.get("data"), "snapshot data").get("universes")
    if not isinstance(universe_rows, list):
        raise AuthorityError("snapshot universes are invalid")
    ready = {
        row.get("universe_id")
        for row in universe_rows
        if isinstance(row, dict) and row.get("research_draft_eligible") is True
    }
    if ready != set(authority.get("eligible_universe_ids", [])):
        raise AuthorityError("eligible universe set drifted from the pinned snapshot")
    return snapshot


def _load_families(root: Path, config: dict[str, Any]) -> dict[str, FamilyRule]:
    rows = config.get("research_families")
    if not isinstance(rows, list) or not rows:
        raise AuthorityError("research family registry is missing")
    families: dict[str, FamilyRule] = {}
    for row in rows:
        row = _expect_dict(row, "research family")
        multiplicity = _expect_dict(row.get("multiplicity_context"), "multiplicity context")
        primary = _load_scope(root, multiplicity.get("primary"), "primary")
        sensitivity_value = multiplicity.get("sensitivity")
        sensitivity = (
            None if sensitivity_value is None else _load_scope(root, sensitivity_value, "sensitivity")
        )
        family_id = str(row.get("family_id"))
        if family_id in families:
            raise AuthorityError("duplicate research family")
        families[family_id] = FamilyRule(
            family_id=family_id,
            hypothesis_id=str(row.get("hypothesis_id")),
            falsification_rule_id=str(row.get("falsification_rule_id")),
            allowed_generation_modes=tuple(row.get("allowed_generation_modes", [])),
            primary=primary,
            sensitivity=sensitivity,
            planned_increment_policy=str(multiplicity.get("planned_increment_policy")),
        )
    return families


def _load_scope(root: Path, value: Any, name: str) -> MultiplicityScope:
    scope = _expect_dict(value, f"{name} multiplicity scope")
    path = str(scope.get("evidence_path"))
    expected_sha = str(scope.get("evidence_sha256"))
    _verify_file(root, path, expected_sha)
    prior = int(scope.get("prior_attempt_count", -1))
    if prior < 0 or not scope.get("scope_id"):
        raise AuthorityError(f"{name} multiplicity scope is incomplete")
    return MultiplicityScope(
        scope_id=str(scope["scope_id"]),
        prior_attempt_count=prior,
        evidence_path=path,
        evidence_sha256=expected_sha,
    )


def _verify_generation_contracts(config: dict[str, Any]) -> None:
    expected = {
        "DETERMINISTIC_CODE": {
            "provider_identity": "NONE_NOT_APPLICABLE",
            "provider_call_intent_policy": "MUST_EQUAL_ZERO",
            "completed_response_target_policy": "MUST_EQUAL_ZERO",
            "provider_budget_usd_policy": "MUST_EQUAL_ZERO",
            "planned_attempt_policy": "GENERATION_ATTEMPT_CAP_COUNTS_ONCE",
        },
        "LLM_BOUNDED_DSL": {
            "provider_identity": "TO_BE_REVIEWED_NOT_AUTHORIZED",
            "provider_call_intent_policy": "MUST_EQUAL_GENERATION_ATTEMPT_CAP",
            "completed_response_target_policy": "MUST_EQUAL_GENERATION_ATTEMPT_CAP",
            "provider_budget_usd_policy": "MUST_BE_POSITIVE_UP_TO_MAXIMUM",
            "planned_attempt_policy": "GENERATION_ATTEMPT_CAP_COUNTS_ONCE",
            "failed_attempts_count": True,
            "replacement_attempts_authorized": False,
        },
    }
    if config.get("generation_mode_contracts") != expected:
        raise AuthorityError("generation mode contract drifted")


def load_authority(project_root: Path) -> AuthorityBundle:
    """Load and physically verify every authority input used by proposals."""
    root = project_root.resolve(strict=True)
    config, _ = _load_config(root)
    protocol = _expect_dict(config.get("base_protocol"), "base protocol")
    correction = _expect_dict(config.get("correction_protocol"), "correction protocol")
    superseded = _expect_dict(config.get("superseded_config"), "superseded config")
    adr = _expect_dict(config.get("adr"), "adr")
    constitution = _expect_dict(config.get("architecture_constitution"), "architecture constitution")
    _verify_file(root, str(protocol.get("path")), str(protocol.get("sha256")))
    _verify_file(root, str(correction.get("path")), str(correction.get("sha256")))
    _verify_file(root, str(superseded.get("path")), str(superseded.get("sha256")))
    _verify_file(root, str(adr.get("path")), str(adr.get("sha256")))
    if superseded.get("status") != "SUPERSEDED_BEFORE_IMPLEMENTATION":
        raise AuthorityError("v1 config is not explicitly superseded")
    if (
        constitution.get("path") != str(CONSTITUTION_RELATIVE_PATH)
        or constitution.get("sha256") != CONSTITUTION_SHA256
    ):
        raise AuthorityError("architecture constitution identity is invalid")
    _verify_file(root, str(constitution["path"]), str(constitution["sha256"]))
    authority = _expect_dict(config.get("authority"), "authority")
    _verify_file(root, REGISTRY_RELATIVE_PATH, str(authority.get("universe_registry_sha256")))
    _verify_snapshot(root, config)
    _verify_generation_contracts(config)
    families = _load_families(root, config)
    try:
        fixed = FixedAuthority.model_validate(config.get("fixed_authority"))
    except ValidationError as exc:
        raise AuthorityError("fixed authority contract is invalid") from exc
    identity = {
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "protocol_sha256": protocol.get("sha256"),
        "correction_protocol_sha256": correction.get("sha256"),
        "superseded_config_sha256": superseded.get("sha256"),
        "adr_sha256": adr.get("sha256"),
        "constitution_sha256": CONSTITUTION_SHA256,
        "snapshot_sha256": authority.get("snapshot_sha256"),
        "authority_addendum_sha256": authority.get("authority_addendum_sha256"),
        "universe_registry_sha256": authority.get("universe_registry_sha256"),
        "multiplicity_evidence": {
            family_id: {
                "primary": rule.primary.evidence_sha256,
                "sensitivity": rule.sensitivity.evidence_sha256 if rule.sensitivity else None,
            }
            for family_id, rule in families.items()
        },
    }
    return AuthorityBundle(
        project_root=root,
        config=config,
        config_sha256=EXPECTED_CONFIG_SHA256,
        authority_bundle_sha256=sha256_text(canonical_json(identity)),
        snapshot_id=str(authority["snapshot_id"]),
        snapshot_sha256=str(authority["snapshot_sha256"]),
        eligible_universe_ids=tuple(authority["eligible_universe_ids"]),
        blocked_universe_ids=tuple(authority["blocked_universe_ids"]),
        families=families,
        fixed_authority=fixed,
    )
