"""Frozen inputs and result-blind candidate registry for TS-v5-R3G."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_bound_proposal_contract import (
    compile_bound_proposal,
    independent_authority,
)
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_models import Mechanism, MechanismCandidate, ParameterSlot

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3g_executable_semantics_engineering_v1.yaml"
SCOPE_SHA256 = "3a066c13eeefd9409c159973a5ae1aff63fb5fc92b8caa67275ae5790b1345bb"
REFERENCE_ADDENDUM_PATH = PROJECT_ROOT / "config/ts_v5_r3g_reference_dimension_addendum_v1.yaml"
REFERENCE_ADDENDUM_SHA256 = "945abec5a281bad3ff5d888a8dcb06eb416578a8190131d3850b332c6dabd1f0"
CONFIRMATION_ADDENDUM_PATH = (
    PROJECT_ROOT / "config/ts_v5_r3g_confirmation_binding_addendum_v1.yaml"
)
CONFIRMATION_ADDENDUM_SHA256 = "26e856576b036abea1e96f7a3e57cc27a8ceb74aec31fec4b440a68e0b17b48f"
R3F_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3f-canary-001"
ATTEMPT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_r3f_llm_attempts.csv"


@dataclass(frozen=True)
class RegisteredCandidate:
    ordinal: int
    attempt_id: str
    candidate: MechanismCandidate
    maximum_points: int
    grid: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class R3GScope:
    document: dict[str, Any]
    reference_addendum: dict[str, Any]
    confirmation_addendum: dict[str, Any]
    sha256: str = SCOPE_SHA256

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "R3GScope":
        document = _load_bound_yaml(path, SCOPE_SHA256, "scope")
        reference = _load_bound_yaml(
            REFERENCE_ADDENDUM_PATH, REFERENCE_ADDENDUM_SHA256, "reference addendum"
        )
        confirmation = _load_bound_yaml(
            CONFIRMATION_ADDENDUM_PATH,
            CONFIRMATION_ADDENDUM_SHA256,
            "confirmation addendum",
        )
        authority = document.get("authority", {})
        if (
            document.get("schema_version") != "ts-v5-r3g-executable-semantics-engineering-v1"
            or document.get("status") != "RESULT_BLIND_EXECUTABLE_SEMANTICS_ENGINEERING_FROZEN"
            or document.get("production_authorization") != "none"
            or authority.get("read_market_or_security_data") is not False
            or authority.get("read_post_entry_return_or_effect") is not False
            or authority.get("external_network_or_provider") is not False
            or authority.get("env_or_secret_read") is not False
        ):
            raise D1ControlError("TS-v5-R3G scope authority differs")
        if any(
            item.get("binds_scope", {}).get("sha256") != SCOPE_SHA256
            or item.get("production_authorization") != "none"
            for item in (reference, confirmation)
        ):
            raise D1ControlError("TS-v5-R3G addendum binding differs")
        return cls(document, reference, confirmation)


def _load_bound_yaml(path: Path, expected: str, label: str) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != expected:
        raise D1ControlError(f"TS-v5-R3G {label} identity differs")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise D1ControlError(f"TS-v5-R3G {label} is invalid") from exc
    if not isinstance(value, dict):
        raise D1ControlError(f"TS-v5-R3G {label} is not an object")
    return value


def evidence_tree_sha256(root: Path = R3F_ROOT, project_root: Path = PROJECT_ROOT) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(project_root).as_posix()
        digest.update(f"{sha256_file(path)}  {relative}\n".encode())
    return digest.hexdigest()


def verify_frozen_inputs(scope: R3GScope, root: Path = PROJECT_ROOT) -> None:
    frozen = scope.document["frozen_inputs"]
    files = {
        "config/ts_v5_r3f_llm_canary_scope_v1.yaml": frozen["r3f_scope_sha256"],
        "config/ts_v5_r3f_llm_execution_release_v1.yaml": frozen["r3f_release_sha256"],
        "config/ts_v5_mechanism_proposal_v3.yaml": frozen["proposal_contract_sha256"],
        "src/shaiwei/research/trend_swing/v5_bound_proposal_contract.py": frozen[
            "proposal_compiler_sha256"
        ],
        "src/shaiwei/research/trend_swing/v5_models.py": frozen["candidate_validator_sha256"],
        "ledger/ts_v5_r3f_llm_attempts.csv": frozen["r3f_attempt_ledger_sha256"],
        "ledger/ts_v5_r3f_llm_transports.csv": frozen["r3f_transport_ledger_sha256"],
        "data/research/trend_swing/ts-v5-r3f-canary-001/ts_v5_r3f_report.json": frozen[
            "r3f_report_sha256"
        ],
        "data/research/trend_swing/ts-v5-r3f-canary-001/ts_v5_r3f_audit.json": frozen[
            "r3f_audit_sha256"
        ],
    }
    for relative, expected in files.items():
        if sha256_file(root / relative) != expected:
            raise D1ControlError(f"TS-v5-R3G frozen input differs: {relative}")
    if evidence_tree_sha256(root / R3F_ROOT.relative_to(PROJECT_ROOT), root) != frozen[
        "r3f_evidence_tree_sha256"
    ]:
        raise D1ControlError("TS-v5-R3G R3F evidence tree differs")


def _ledger_rows(path: Path = ATTEMPT_LEDGER) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if (
        len(rows) != 6
        or [int(row["ordinal"]) for row in rows] != list(range(1, 7))
        or any(
            row["mode"] != "INDEPENDENT"
            or row["parse_status"] != "PASS"
            or row["schema_status"] != "PASS"
            or row["duplicate_status"] != "UNIQUE"
            or row["failure_class"]
            for row in rows
        )
    ):
        raise D1ControlError("TS-v5-R3G R3F attempt ledger differs")
    return rows


def _load_candidate(row: dict[str, str], binding: dict[str, Any], root: Path) -> MechanismCandidate:
    raw_path = root / row["raw_artifact_path"]
    if sha256_file(raw_path) != row["raw_artifact_sha256"]:
        raise D1ControlError("TS-v5-R3G R3F response identity differs")
    try:
        envelope = json.loads(raw_path.read_text(encoding="utf-8"))
        document = json.loads(envelope["content"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise D1ControlError("TS-v5-R3G R3F content is invalid") from exc
    mechanism = Mechanism(row["mechanism"])
    compiled = compile_bound_proposal(
        mechanism,
        document,
        independent_authority(row["attempt_id"], int(row["ordinal"])),
    )
    candidate = compiled.candidate
    observed = (
        row["attempt_id"],
        mechanism.value,
        candidate.fingerprint(),
        candidate.semantic_signature(),
        compiled.search_evaluations,
    )
    expected = (
        binding["attempt_id"],
        binding["mechanism"],
        binding["candidate_fingerprint"],
        binding["semantic_signature"],
        binding["maximum_search_budget_points"],
    )
    if observed != expected or observed[2:4] != (
        row["candidate_fingerprint"], row["semantic_signature"]
    ):
        raise D1ControlError("TS-v5-R3G candidate binding differs")
    return candidate


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


def slot_values(slot: ParameterSlot) -> tuple[str, ...]:
    low, high = Decimal(slot.minimum), Decimal(slot.maximum)
    count = slot.search_points_maximum
    if slot.value_type == "INTEGER":
        count = min(count, int(high - low) + 1)
        values = {
            (low + (high - low) * index / (count - 1)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            for index in range(count)
        }
        values.update({low, high})
        return tuple(_decimal_text(value) for value in sorted(values))
    return tuple(
        _decimal_text(low + (high - low) * index / (count - 1))
        for index in range(count)
    )


def parameter_grid(candidate: MechanismCandidate) -> tuple[dict[str, str], ...]:
    slots = sorted(candidate.parameter_slots, key=lambda item: item.parameter_id.value)
    names = [slot.parameter_id.value for slot in slots]
    return tuple(
        dict(zip(names, values, strict=True))
        for values in itertools.product(*(slot_values(slot) for slot in slots))
    )


def registered_candidates(scope: R3GScope, root: Path = PROJECT_ROOT) -> tuple[RegisteredCandidate, ...]:
    verify_frozen_inputs(scope, root)
    rows = _ledger_rows(root / ATTEMPT_LEDGER.relative_to(PROJECT_ROOT))
    bindings = scope.document["candidate_bindings"]
    registered = []
    for row, binding in zip(rows, bindings, strict=True):
        candidate = _load_candidate(row, binding, root)
        grid = parameter_grid(candidate)
        if len(grid) != binding["expected_effective_grid_points"] or len({
            canonical_json(item) for item in grid
        }) != len(grid):
            raise D1ControlError("TS-v5-R3G effective parameter grid differs")
        registered.append(RegisteredCandidate(
            int(row["ordinal"]), row["attempt_id"], candidate,
            int(binding["maximum_search_budget_points"]), grid,
        ))
    if sum(len(item.grid) for item in registered) != 431:
        raise D1ControlError("TS-v5-R3G total effective parameter grid differs")
    return tuple(registered)


def sanitized_registry(scope: R3GScope, candidates: tuple[RegisteredCandidate, ...]) -> dict[str, Any]:
    entries = []
    for item in candidates:
        candidate = item.candidate
        entries.append({
            "candidate_id": f"ts-v5-r3g-c{item.ordinal:02d}",
            "ordinal": item.ordinal,
            "attempt_id": item.attempt_id,
            "mechanism": candidate.primary_mechanism.value,
            "candidate_fingerprint": candidate.fingerprint(),
            "semantic_signature": candidate.semantic_signature(),
            "entry_design": candidate.entry_design.model_dump(mode="json"),
            "required_features": sorted(item.value for item in candidate.required_features),
            "parameter_grid_sha256": sha256_text(canonical_json(item.grid)),
            "maximum_search_budget_points": item.maximum_points,
            "effective_grid_points": len(item.grid),
            "parameter_slots": [
                {
                    **slot.model_dump(mode="json"),
                    "effective_values": list(slot_values(slot)),
                }
                for slot in sorted(candidate.parameter_slots, key=lambda row: row.parameter_id.value)
            ],
            "candidate_effectiveness": "NOT_EVALUATED",
        })
    return {
        "schema_version": "ts-v5-r3g-sanitized-candidate-registry-v1",
        "scope_sha256": scope.sha256,
        "reference_addendum_sha256": REFERENCE_ADDENDUM_SHA256,
        "confirmation_addendum_sha256": CONFIRMATION_ADDENDUM_SHA256,
        "candidate_count": len(entries),
        "effective_parameter_point_count": sum(row["effective_grid_points"] for row in entries),
        "cumulative_llm_generation_attempts": 28,
        "prior_strategy_effect_attempts": 0,
        "entries": entries,
        "market_security_or_effect_read": False,
        "production_authorization": "none",
    }
