"""Hash the exact pushed files entering the M7 lineage image and release."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import sha256_file, sha256_json

from .contract import LineageError


FIXED_FILES = (
    ".dockerignore",
    "Dockerfile.m7-moneyflow-gap-lineage",
    "compose.m7-moneyflow-gap-lineage.yaml",
    "requirements.m5-data-gate.lock",
    "src/shaiwei/__init__.py",
    "config/m7_moneyflow_gap_lineage_v1.yaml",
    "config/m7_moneyflow_gap_lineage_input_manifest_v1.json",
    "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_protocol_scope_v1.json",
    "config/m7_star_custom_pool_moneyflow_proposal_export_v1.json",
    "config/m3_star_custom_pit_v1.yaml",
    "config/m3_star_custom_pit_manifest_v1.json",
    "config/m7_moneyflow_recovery_engineering_v1.yaml",
    "docs/M7_MONEYFLOW_GAP_LINEAGE_PROTOCOL_20260809.md",
    "docs/M7_MONEYFLOW_RECOVERY_ENGINEERING_ACCEPTANCE_20260808.md",
    "docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_COMPATIBILITY_PROTOCOL_20260808.md",
    "docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_PROTOCOL_FREEZE_ACCEPTANCE_20260808.md",
    "tools/m7_moneyflow_lineage_approval.py",
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise LineageError("lineage Git identity check failed")
    return result.stdout.strip()


def build_implementation_identity(root: Path) -> dict[str, Any]:
    dynamic = sorted(
        path.relative_to(root).as_posix()
        for package in (
            root / "src/shaiwei/research_gates/m7_moneyflow",
            root / "src/shaiwei/research_gates/m7_moneyflow_lineage",
        )
        for path in package.glob("*.py")
        if path.is_file()
    )
    paths = [*FIXED_FILES, *dynamic]
    if len(paths) != len(set(paths)) or any(not (root / item).is_file() for item in paths):
        raise LineageError("lineage implementation bundle is incomplete")
    head = _git(root, "rev-parse", "HEAD")
    origin = _git(root, "rev-parse", "origin/main")
    if head != origin:
        raise LineageError("lineage implementation is not synchronized with origin/main")
    if _git(root, "diff", "--name-only", "HEAD", "--", *paths):
        raise LineageError("lineage implementation differs from pushed commit")
    tracked = set(_git(root, "ls-files", "--cached", "--", *paths).splitlines())
    if tracked != set(paths):
        raise LineageError("lineage implementation contains untracked files")
    files = [{"path": item, "sha256": sha256_file(root / item)} for item in paths]
    return {
        "git_commit": head,
        "origin_main_commit": origin,
        "commit_pushed_before_scope": True,
        "code_bundle_sha256": sha256_json(files),
        "requirements_lock_sha256": sha256_file(root / "requirements.m5-data-gate.lock"),
        "dockerfile_sha256": sha256_file(root / "Dockerfile.m7-moneyflow-gap-lineage"),
        "compose_sha256": sha256_file(root / "compose.m7-moneyflow-gap-lineage.yaml"),
        "auditor_code_sha256": sha256_file(
            root / "src/shaiwei/research_gates/m7_moneyflow_lineage/auditor.py"
        ),
        "approval_builder_sha256": sha256_file(root / "tools/m7_moneyflow_lineage_approval.py"),
    }
