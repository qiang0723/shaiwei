"""Identity-first loader for the sealed R2 Head30 targets and ideal daily path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import mapping

from .release_contract import ReleaseScope


WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")
EXPECTED_FILES = {
    "authorization.json", "treatment_effect_started.json", "first_pass/bundle.json",
    "replay/bundle.json", "report.json",
}


def verify_tree(root: Path, release: ReleaseScope) -> dict[str, Any]:
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual_files != EXPECTED_FILES:
        raise ProtocolError("M6-5B sealed R2 file set differs")
    observed = effect_tree_identity(root)
    expected = release.scope["inputs"]["sealed_r2"]
    if observed != {key: expected[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("M6-5B sealed R2 tree differs")
    return observed


def _validate_bundle(bundle: dict[str, Any]) -> None:
    treatments = bundle.get("treatments")
    if not isinstance(treatments, dict) or tuple(treatments) != WINDOWS:
        raise ProtocolError("M6-5B sealed R2 window set differs")
    for window, treatment in treatments.items():
        if not isinstance(treatment, dict) or not treatment.get("daily"):
            raise ProtocolError(f"M6-5B sealed R2 daily path absent: {window}")
        for row in treatment.get("rebalances", []):
            targets = row.get("targets")
            if not isinstance(targets, list) or len(targets) != 30 or len(set(targets)) != 30:
                raise ProtocolError("M6-5B sealed target count differs")
            if any(str(code).startswith("BJ") or str(code).endswith(".BJ") for code in targets):
                raise ProtocolError("M6-5B sealed target contains Beijing security")


def load(root: Path, release: ReleaseScope) -> dict[str, Any]:
    verify_tree(root, release)
    first_path = root / "first_pass/bundle.json"
    replay_path = root / "replay/bundle.json"
    first, replay = mapping(first_path), mapping(replay_path)
    if sha256_file(first_path) != sha256_file(replay_path) or first != replay:
        raise ProtocolError("M6-5B sealed first-pass and replay differ")
    _validate_bundle(first)
    return first
