"""Stable provenance identifiers shared by reports, manifests, and ledgers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid


CONTROLLED_ROOTS = ("src/", "config/", "templates/", "tests/")
CONTROLLED_FILES = {
    ".dockerignore",
    ".env.example",
    "Dockerfile",
    "Dockerfile.ts-v5-llm",
    "Dockerfile.ts-v5-r3g",
    "Dockerfile.ts-v5-r3g1",
    "Dockerfile.ts-v5-r3g2-benchmark",
    "Dockerfile.ts-v6-entry-quality",
    "Dockerfile.ts-v6-1-ranking",
    "Dockerfile.ts-v6-3-ranked-subset",
    "Dockerfile.ts-v6-4-no-takeprofit",
    "Dockerfile.ts-b-holdout",
    "Dockerfile.ts-rf-0b",
    "Dockerfile.ts-rf-diag",
    "Dockerfile.ts-rf-0c",
    "Dockerfile.ts-rf-1",
    "Dockerfile.ts-c-qualification",
    "Dockerfile.ts-c-qualification-v2",
    "docs/M6_CSI800_MODEL_ATTRIBUTION_AUDIT_RECOVERY_ACCEPTANCE_20260807.md",
    "Makefile",
    "compose.yaml",
    "compose.research.yaml",
    "compose.m6-attribution.yaml",
    "compose.m6-topk-conversion-release.yaml",
    "compose.m6-production-head30-release.yaml",
    "compose.m6-production-head30-recovery.yaml",
    "compose.m6-production-head30-price-recovery.yaml",
    "compose.m6-head30-500k-release.yaml",
    "compose.ts-recovery.yaml",
    "compose.ts-v5-r2.yaml",
    "compose.ts-v5-r3c.yaml",
    "compose.ts-v5-r3f.yaml",
    "compose.ts-v5-r3g.yaml",
    "compose.ts-v5-r3g1.yaml",
    "compose.ts-v5-r3g2-benchmark.yaml",
    "compose.ts-v5-r3g2-w7.yaml",
    "compose.ts-v5-r3g2-w7-recovery.yaml",
    "compose.ts-v5-r3g2-effect.yaml",
    "compose.ts-v5-r3g2-effect-recovery.yaml",
    "compose.ts-v5-r3g3-diagnostic.yaml",
    "compose.ts-v6-entry-quality.yaml",
    "compose.ts-v6-1-ranking.yaml",
    "compose.ts-v6-3-ranked-subset.yaml",
    "compose.ts-v6-4-no-takeprofit.yaml",
    "compose.ts-b-holdout.yaml",
    "compose.ts-rf-0b.yaml",
    "compose.ts-rf-diag.yaml",
    "compose.ts-rf-0c.yaml",
    "compose.ts-rf-1.yaml",
    "compose.ts-c-qualification.yaml",
    "compose.ts-c-qualification-v2.yaml",
    "compose.ts-v5-llm.yaml",
    "pyproject.toml",
    "requirements.lock",
    "requirements.ts-v5-llm.lock",
}
RELEASE_MANIFEST_ENV = "SHAIWEI_RELEASE_MANIFEST"
RELEASE_GIT_HEAD_ENV = "SHAIWEI_RELEASE_GIT_HEAD"
RELEASE_MANIFEST_SCHEMA = "shaiwei-release-manifest-v1"
_IGNORED_TREE_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def _is_controlled_input(name: str) -> bool:
    return name in CONTROLLED_FILES or name.startswith(CONTROLLED_ROOTS)


def _is_ignored_tree_path(path: Path) -> bool:
    return (
        any(part in _IGNORED_TREE_PARTS or part.endswith(".egg-info") for part in path.parts)
        or path.name == ".DS_Store"
        or path.suffix in {".pyc", ".pyo"}
    )


def _snapshot_payload(root: Path, names: list[str]) -> tuple[str, list[dict[str, str]]]:
    payload = hashlib.sha256()
    records: list[dict[str, str]] = []
    for name in sorted(names):
        path = root / name
        if not path.is_file():
            continue
        if path.is_symlink():
            raise RuntimeError(f"controlled release input must not be a symlink: {name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        payload.update(name.encode("utf-8"))
        payload.update(b"\0")
        payload.update(bytes.fromhex(digest))
        records.append({"path": name, "sha256": digest})
    return payload.hexdigest(), records


def controlled_tree_names(root: Path) -> list[str]:
    """List the exact controlled files copied into an immutable release image."""
    names = {name for name in CONTROLLED_FILES if (root / name).is_file()}
    for prefix in CONTROLLED_ROOTS:
        directory = root / prefix.rstrip("/")
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and not _is_ignored_tree_path(relative):
                names.add(relative.as_posix())
    return sorted(names)


def write_release_manifest(path: Path, *, root: Path | None = None) -> dict[str, object]:
    """Write a content-addressed manifest for the image's controlled source tree."""
    project_root = (root or Path.cwd()).resolve()
    snapshot, files = _snapshot_payload(project_root, controlled_tree_names(project_root))
    document: dict[str, object] = {
        "schema_version": RELEASE_MANIFEST_SCHEMA,
        "code_snapshot_sha256": snapshot,
        "file_count": len(files),
        "files": files,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return document


def verify_release_manifest(path: Path, *, root: Path | None = None) -> str:
    """Fail closed unless every embedded controlled file matches the release manifest."""
    project_root = (root or Path.cwd()).resolve()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("release manifest is missing or invalid") from error
    if not isinstance(document, dict) or document.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise RuntimeError("release manifest schema is invalid")
    raw_files = document.get("files")
    if not isinstance(raw_files, list):
        raise RuntimeError("release manifest files must be a list")
    records: list[dict[str, str]] = []
    for raw in raw_files:
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("path"), str)
            or not isinstance(raw.get("sha256"), str)
        ):
            raise RuntimeError("release manifest contains an invalid file record")
        records.append({"path": raw["path"], "sha256": raw["sha256"]})
    expected_names = [record["path"] for record in records]
    if len(expected_names) != len(set(expected_names)):
        raise RuntimeError("release manifest contains duplicate paths")
    if expected_names != sorted(expected_names):
        raise RuntimeError("release manifest paths are not canonical")
    actual_names = controlled_tree_names(project_root)
    if actual_names != expected_names:
        raise RuntimeError("release controlled-file set differs from the embedded manifest")
    snapshot, actual_records = _snapshot_payload(project_root, actual_names)
    if actual_records != records:
        raise RuntimeError("release controlled-file content differs from the embedded manifest")
    if document.get("file_count") != len(records):
        raise RuntimeError("release manifest file count differs")
    if document.get("code_snapshot_sha256") != snapshot:
        raise RuntimeError("release manifest snapshot digest differs")
    return snapshot


def git_head() -> str:
    release_head = os.getenv(RELEASE_GIT_HEAD_ENV, "").strip().lower()
    if release_head:
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", release_head) is None:
            raise RuntimeError("embedded release Git revision is invalid")
        return release_head
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head) is None:
        raise RuntimeError("Git returned an invalid revision")
    return head


def code_snapshot_sha256() -> str:
    """Hash executable, configuration, dependency, template, and test inputs.

    HEAD and documentation/status/evidence files are intentionally absent:
    committing or backfilling an unchanged run must not invalidate its reports.
    """
    if release_manifest := os.getenv(RELEASE_MANIFEST_ENV):
        return verify_release_manifest(Path(release_manifest))
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True
    ).stdout.split(b"\0")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    names = sorted(
        name.decode("utf-8")
        for name in {*tracked, *untracked}
        if name and _is_controlled_input(name.decode("utf-8"))
    )
    snapshot, _ = _snapshot_payload(Path.cwd(), names)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-release-manifest", type=Path)
    parser.add_argument("--verify-release-manifest", type=Path)
    args = parser.parse_args(argv)
    if bool(args.write_release_manifest) == bool(args.verify_release_manifest):
        parser.error("choose exactly one release-manifest action")
    if args.write_release_manifest:
        document = write_release_manifest(args.write_release_manifest)
        print(document["code_snapshot_sha256"])
    else:
        print(verify_release_manifest(args.verify_release_manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
