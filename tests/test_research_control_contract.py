from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from shaiwei.research_control.authority import (
    CONFIG_RELATIVE_PATH,
    EXPECTED_CONFIG_SHA256,
    AuthorityError,
    load_authority,
)
from shaiwei.research_control.models import ProposalCreate
from shaiwei.research_control.storage import EXPECTED_TABLES, SQLiteStore, StorageError

ROOT = Path(__file__).parents[1]
ACTOR = hashlib.sha256(b"m5-local-research-proposer-v1").hexdigest()


def valid_payload(mode: str = "DETERMINISTIC_CODE") -> dict:
    authority = load_authority(ROOT)
    provider = mode == "LLM_BOUNDED_DSL"
    return {
        "template_id": "bounded-research-proposal-v1",
        "template_version": 2,
        "universe_ids": ["csi800-pit-v1", "star50-official-pit-v2"],
        "home_universe_id": "csi800-pit-v1",
        "family_id": "moneyflow",
        "hypothesis_id": "incremental-flow-information-v1",
        "falsification_rule_id": "frozen-gates-reject-v1",
        "generation_mode": mode,
        "generation_attempt_cap": 8,
        "candidate_cap": 4,
        "provider_identity": "TO_BE_REVIEWED_NOT_AUTHORIZED" if provider else "NONE_NOT_APPLICABLE",
        "provider_call_intent_count": 8 if provider else 0,
        "completed_response_target": 8 if provider else 0,
        "provider_budget_usd": "0.25" if provider else "0.00",
        "valid_days": 7,
        "authority": authority.fixed_authority.model_dump(mode="json"),
    }


def _copy_authority_tree(target: Path) -> None:
    config = yaml.safe_load((ROOT / CONFIG_RELATIVE_PATH).read_text(encoding="utf-8"))
    relatives = {
        CONFIG_RELATIVE_PATH,
        Path(config["base_protocol"]["path"]),
        Path(config["correction_protocol"]["path"]),
        Path(config["superseded_config"]["path"]),
        Path(config["adr"]["path"]),
        Path(config["architecture_constitution"]["path"]),
        Path("config/m1_multi_universe_v1.yaml"),
        Path(config["authority"]["strategy_factory_root"])
        / "snapshots"
        / f"{config['authority']['snapshot_id']}.json",
    }
    for family in config["research_families"]:
        context = family["multiplicity_context"]
        relatives.add(Path(context["primary"]["evidence_path"]))
        if context["sensitivity"]:
            relatives.add(Path(context["sensitivity"]["evidence_path"]))
    for relative in relatives:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)


def test_v2_authority_is_fully_bound_and_multiplicity_is_not_flattened():
    authority = load_authority(ROOT)

    assert CONFIG_RELATIVE_PATH.name.endswith("v2.yaml")
    assert authority.config_sha256 == EXPECTED_CONFIG_SHA256
    assert authority.families["fundamental_static"].primary.prior_attempt_count == 6
    assert authority.families["fundamental_static"].sensitivity.prior_attempt_count == 12
    assert authority.families["residual_risk"].primary.prior_attempt_count == 3
    assert authority.families["residual_risk"].sensitivity.prior_attempt_count == 273
    assert authority.fixed_authority.approval_authorized is False
    assert authority.fixed_authority.provider_spend_authorized is False


def test_v1_selection_or_any_bound_file_drift_fails_closed(tmp_path: Path):
    _copy_authority_tree(tmp_path)
    constitution = tmp_path / "docs/ARCHITECTURE_CONSTITUTION.md"
    constitution.write_text(constitution.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
    with pytest.raises(AuthorityError):
        load_authority(tmp_path)

    _copy_authority_tree(tmp_path)
    shutil.copyfile(ROOT / "config/m5_research_proposal_control_v1.yaml", tmp_path / CONFIG_RELATIVE_PATH)
    with pytest.raises(AuthorityError):
        load_authority(tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_call_intent_count", 1),
        ("completed_response_target", 1),
        ("provider_budget_usd", "0.01"),
        ("provider_identity", "TO_BE_REVIEWED_NOT_AUTHORIZED"),
    ],
)
def test_deterministic_provider_cross_fields_are_all_zero(field: str, value: object):
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        ProposalCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_call_intent_count", 0),
        ("completed_response_target", 0),
        ("provider_budget_usd", "0.00"),
        ("provider_identity", "NONE_NOT_APPLICABLE"),
    ],
)
def test_llm_provider_cross_fields_must_match_bounded_attempts(field: str, value: object):
    payload = valid_payload("LLM_BOUNDED_DSL")
    payload[field] = value
    with pytest.raises(ValidationError):
        ProposalCreate.model_validate(payload)


def test_contract_rejects_unknown_code_url_secret_and_authority_true():
    payload = valid_payload()
    payload["unknown"] = "value"
    with pytest.raises(ValidationError):
        ProposalCreate.model_validate(payload)
    for malicious in ("https://example.invalid", "../secret", "sk-1234567890abcdef"):
        changed = valid_payload()
        changed["hypothesis_id"] = malicious
        with pytest.raises(ValidationError):
            ProposalCreate.model_validate(changed)
    changed = valid_payload()
    changed["authority"]["approval_authorized"] = True
    with pytest.raises(ValidationError):
        ProposalCreate.model_validate(changed)


def test_schema_has_only_three_tables_and_immutability_triggers(tmp_path: Path):
    path = tmp_path / "control.sqlite3"
    SQLiteStore(path)
    connection = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert tables == EXPECTED_TABLES
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        connection.close()


def test_unknown_or_corrupt_database_refuses_startup(tmp_path: Path):
    unknown = tmp_path / "unknown.sqlite3"
    connection = sqlite3.connect(unknown)
    connection.execute("PRAGMA user_version=2")
    connection.close()
    with pytest.raises(StorageError):
        SQLiteStore(unknown)

    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(StorageError):
        SQLiteStore(corrupt)


@pytest.mark.parametrize(
    "mutation_sql",
    [
        "DROP TRIGGER events_no_delete",
        "DROP TABLE proposal_events; CREATE TABLE proposal_events(fake TEXT)",
        "ALTER TABLE proposals ADD COLUMN unexpected TEXT",
        "DROP INDEX proposals_actor_created",
    ],
)
def test_frozen_schema_fingerprint_rejects_trigger_table_column_or_index_drift(
    tmp_path: Path, mutation_sql: str
):
    path = tmp_path / "drift.sqlite3"
    SQLiteStore(path)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(mutation_sql)
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(StorageError):
        SQLiteStore(path)
