"""Hash the exact committed source and container files in the M7 release image."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .contract import M7GateError, sha256_file, sha256_json


FIXED_FILES = (
    ".dockerignore",
    "Dockerfile.m7-moneyflow-data-gate",
    "compose.m7-moneyflow-gate.yaml",
    "requirements.m5-data-gate.lock",
    "src/shaiwei/__init__.py",
    "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
    "config/m7_star_custom_pool_moneyflow_protocol_scope_v1.json",
    "config/m7_star_custom_pool_moneyflow_proposal_export_v1.json",
    "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
    "config/m3_star_custom_pit_v1.yaml",
    "config/m3_star_custom_pit_manifest_v1.json",
    "docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_COMPATIBILITY_PROTOCOL_20260808.md",
    "docs/M7_STAR_CUSTOM_POOL_MONEYFLOW_PROTOCOL_FREEZE_ACCEPTANCE_20260808.md",
)


def _git(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise M7GateError("M7 implementation Git identity check failed")
    return result.stdout.strip()


def build_implementation_identity(project_root: Path) -> dict[str, Any]:
    dynamic_files = sorted(
        path.relative_to(project_root).as_posix()
        for path in (project_root / "src/shaiwei/research_gates/m7_moneyflow").glob("*.py")
        if path.is_file()
    )
    paths = [*FIXED_FILES, *dynamic_files]
    if len(paths) != len(set(paths)) or any(not (project_root / path).is_file() for path in paths):
        raise M7GateError("M7 implementation bundle paths are incomplete or duplicated")
    head = _git(project_root, "rev-parse", "HEAD")
    origin = _git(project_root, "rev-parse", "origin/main")
    if head != origin:
        raise M7GateError("M7 implementation commit is not synchronized with origin/main")
    changed = _git(project_root, "diff", "--name-only", "HEAD", "--", *paths)
    if changed:
        raise M7GateError("M7 implementation files differ from the pushed commit")
    tracked = set(_git(project_root, "ls-files", "--cached", "--", *paths).splitlines())
    if tracked != set(paths):
        raise M7GateError("M7 implementation bundle contains an untracked or missing file")
    files = [{"path": path, "sha256": sha256_file(project_root / path)} for path in paths]
    return {
        "schema_version": "m7-moneyflow-implementation-bundle-v1",
        "git_commit": head,
        "origin_main_commit": origin,
        "file_count": len(files),
        "files": files,
        "code_bundle_sha256": sha256_json(files),
    }
