"""Frozen TS-v5 R3G-2 protocol and immutable-input validation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_effect_v1.yaml"
EXPECTED_STATUS = "RESULT_BLIND_EFFECT_PROTOCOL_FROZEN_PENDING_ENGINEERING_RELEASE"


class R3G2Error(RuntimeError):
    """Fail-closed R3G-2 contract violation."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise R3G2Error(f"R3G-2 document is missing or invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G2Error(f"R3G-2 document is not a mapping: {path.name}")
    return value


def project_path(value: str, *, root: Path = PROJECT_ROOT) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise R3G2Error("R3G-2 path escapes the project root") from error
    if path.is_symlink():
        raise R3G2Error("R3G-2 bound path cannot be a symlink")
    return path


def _validate_static(document: Mapping[str, Any]) -> None:
    if document.get("schema_version") != "ts-v5-r3g2-effect-protocol-v1":
        raise R3G2Error("R3G-2 protocol schema differs")
    if document.get("status") != EXPECTED_STATUS:
        raise R3G2Error("R3G-2 protocol status differs")
    if document.get("production_authorization") != "none":
        raise R3G2Error("R3G-2 protocol cannot authorize production")
    authority = document.get("authority_at_freeze", {})
    enabled = {
        key for key, value in authority.items() if isinstance(value, bool) and value
    }
    if enabled != {"protocol_and_contract_tests"}:
        raise R3G2Error("R3G-2 freeze authority was broadened")
    points = document.get("selected_effect_points", {})
    hashes = [points.get("primary_anchor", {}).get("point_hash")]
    hashes.extend(row.get("point_hash") for row in points.get("sensitivity_neighbours", []))
    if hashes != [
        "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784",
        "09bceb50259b20a82b8af30c41d24af7e2b543ff78790aa893c814f72dfc2ea5",
        "355926341879e2a55dc3268d9e0f80c3a82bae5c56c96f59516087b365ac8076",
    ]:
        raise R3G2Error("R3G-2 selected point set differs")
    if document.get("attempt_and_firewall", {}).get(
        "strategy_effect_attempt_count_on_first_effect_read"
    ) != 3:
        raise R3G2Error("R3G-2 effect attempt count differs")


@dataclass(frozen=True)
class EffectProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "EffectProtocol":
        resolved = path.resolve()
        document = _mapping(resolved)
        _validate_static(document)
        return cls(path=resolved, document=document, sha256=sha256_file(resolved))

    @property
    def selected_point_hashes(self) -> tuple[str, str, str]:
        points = self.document["selected_effect_points"]
        return (
            points["primary_anchor"]["point_hash"],
            *(row["point_hash"] for row in points["sensitivity_neighbours"]),
        )

    def m6_document(self) -> dict[str, Any]:
        lineage = self.document["ranking_lineage"]["clean_m6_lineage"]
        path = project_path(lineage["protocol_path"])
        if sha256_file(path) != lineage["protocol_sha256"]:
            raise R3G2Error("R3G-2 M6 protocol hash differs")
        return _mapping(path)

    def w7_window(self) -> dict[str, Any]:
        frozen = self.document["ranking_lineage"]["frozen_w7_extension"]
        return {
            "name": "W7",
            "train": list(frozen["train"]),
            "purged_train_last_signal": frozen["purged_train_last_signal"],
            "valid": list(frozen["valid"]),
            "purged_valid_last_signal": frozen["purged_valid_last_signal"],
            "test": list(frozen["test"]),
            "score_last_signal": frozen["score_last_mature_signal_for_metric_only"],
        }

    def _input_bindings(self, *, include_disallowed_reference: bool) -> list[tuple[str, str]]:
        bindings: list[tuple[str, str]] = []
        for row in self.document["predecessors"].values():
            if isinstance(row, dict) and {"path", "sha256"} <= set(row):
                bindings.append((row["path"], row["sha256"]))
        benchmark = self.document["benchmark"]
        bindings.append((benchmark["path"], benchmark["sha256"]))
        lineage = self.document["ranking_lineage"]
        if include_disallowed_reference:
            bindings.append(
                (lineage["old_p1_cache"]["path"], lineage["old_p1_cache"]["sha256"])
            )
        clean = lineage["clean_m6_lineage"]
        bindings.append((clean["protocol_path"], clean["protocol_sha256"]))
        for row in clean["reusable_predictions"].values():
            bindings.append((row["path"], row["sha256"]))
        return bindings

    def _validate_bindings(self, bindings: list[tuple[str, str]]) -> dict[str, str]:
        observed: dict[str, str] = {}
        for relative, expected in bindings:
            path = project_path(relative)
            if not path.is_file():
                raise R3G2Error(f"R3G-2 bound input is absent: {relative}")
            actual = sha256_file(path)
            if actual != expected:
                raise R3G2Error(f"R3G-2 bound input hash differs: {relative}")
            observed[relative] = actual
        return observed

    def validate_bound_inputs(self) -> dict[str, str]:
        return self._validate_bindings(
            self._input_bindings(include_disallowed_reference=True)
        )

    def bound_input_contract(self) -> dict[str, str]:
        """Return frozen path/hash claims without opening data-bearing inputs."""
        return dict(self._input_bindings(include_disallowed_reference=True))

    def validate_authorized_effect_inputs(self) -> dict[str, str]:
        """Validate only inputs that the real-effect runtime may actually mount."""
        return self._validate_bindings(
            self._input_bindings(include_disallowed_reference=False)
        )
