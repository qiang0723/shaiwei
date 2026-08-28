"""Prepare an isolated, content-addressed scheduler Docker build context."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shaiwei.provenance import (
    CONTROLLED_FILES,
    CONTROLLED_ROOTS,
    controlled_tree_names,
    write_release_manifest,
)


class ReleaseBuildContextError(RuntimeError):
    """The immutable scheduler source context cannot be prepared safely."""


class ControllerIdentityError(RuntimeError):
    """The host release controller differs from its frozen identity."""


class ControllerIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_base_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    controller_source_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    component_paths: tuple[str, ...]
    component_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_paths(self) -> "ControllerIdentity":
        legacy = {
            "src/shaiwei/release_build_context.py",
            "src/shaiwei/release_guard.py",
            "src/shaiwei/daily_early_release_guard.py",
            "src/shaiwei/r2d_release_guard.py",
        }
        recovery = legacy | {"src/shaiwei/r2d_legacy_boundary.py"}
        fixture = {"src/shaiwei/r2d_fixture_evidence.py"}
        actual = set(self.component_paths)
        valid_inventories = (legacy, recovery, legacy | fixture, recovery | fixture)
        if actual not in valid_inventories or len(self.component_paths) != len(actual):
            raise ValueError("R2D controller component inventory differs")
        return self


@dataclass(frozen=True)
class SchedulerBuildContext:
    path: Path
    git_head: str
    code_snapshot_sha256: str
    file_count: int


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or b"").decode(
            "utf-8", errors="replace"
        ).strip()
        raise ReleaseBuildContextError(
            f"Git source-context command failed: {' '.join(args)}: {detail}"
        ) from error


def _decode_paths(payload: bytes) -> tuple[str, ...]:
    try:
        return tuple(
            item.decode("utf-8") for item in payload.split(b"\0") if item
        )
    except UnicodeDecodeError as error:
        raise ReleaseBuildContextError(
            "Git source context contains a non-UTF-8 path"
        ) from error


def _is_controlled_path(path: str) -> bool:
    return path in CONTROLLED_FILES or path.startswith(CONTROLLED_ROOTS)


def _controlled_git_names(root: Path, revision: str) -> tuple[str, ...]:
    names = _decode_paths(_git(root, "ls-tree", "-r", "--name-only", "-z", revision))
    controlled = tuple(sorted(name for name in names if _is_controlled_path(name)))
    if not controlled:
        raise ReleaseBuildContextError("Git revision has no controlled release inputs")
    return controlled


def _controlled_changes(root: Path) -> tuple[str, ...]:
    tracked = _decode_paths(
        _git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD", "--")
    )
    untracked = _decode_paths(
        _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    )
    return tuple(sorted({path for path in (*tracked, *untracked) if _is_controlled_path(path)}))


def _revision(root: Path, name: str) -> str:
    value = _git(root, "rev-parse", "--verify", name).decode("ascii").strip().lower()
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ReleaseBuildContextError(f"Git revision is invalid: {name}")
    return value


def _require_pushed_clean_controlled_tree(root: Path) -> str:
    head = _revision(root, "HEAD")
    origin_main = _revision(root, "origin/main")
    if head != origin_main:
        raise ReleaseBuildContextError("scheduler release HEAD differs from local origin/main")
    changes = _controlled_changes(root)
    if changes:
        raise ReleaseBuildContextError(
            "scheduler release controlled inputs differ from HEAD: " + ", ".join(changes)
        )
    return head


def controlled_source_status(project_root: Path) -> dict[str, object]:
    """Report pushed revision identity and only release-controlled worktree drift."""
    root = project_root.resolve()
    return {
        "head": _revision(root, "HEAD"),
        "origin_main": _revision(root, "origin/main"),
        "controlled_changes": _controlled_changes(root),
    }


def controller_component_sha256(root: Path, paths: tuple[str, ...]) -> str:
    entries = []
    for path in sorted(paths):
        digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
        entries.append({"path": path, "sha256": digest})
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def collect_controller_evidence(
    root: Path,
    run: Callable[..., subprocess.CompletedProcess[str]],
    identity: ControllerIdentity,
) -> dict[str, object]:
    run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            identity.controller_source_head,
            "HEAD",
        ]
    )
    delta = tuple(
        sorted(
            line
            for line in run(
                [
                    "git",
                    "diff",
                    "--name-only",
                    f"{identity.candidate_base_head}..HEAD",
                    "--",
                ]
            ).stdout.splitlines()
            if line
        )
    )
    return {
        "component_sha256": controller_component_sha256(root, identity.component_paths),
        "delta_paths": delta,
        "delta_sha256": hashlib.sha256("\n".join(delta).encode()).hexdigest(),
    }


def validate_controller_evidence(
    identity: ControllerIdentity,
    evidence: dict[str, object],
) -> None:
    if evidence.get("component_sha256") != identity.component_sha256:
        raise ControllerIdentityError("R2D controller component identity differs")
    delta = evidence.get("delta_paths")
    components = set(identity.component_paths)
    if not isinstance(delta, tuple) or any(
        not (
            path in components
            or path == "STATE.md"
            or path.startswith("docs/")
            or path.startswith("tests/")
            or path.startswith("config/r2d_")
        )
        for path in delta
    ):
        raise ControllerIdentityError(
            "candidate-to-controller delta escapes the frozen allowlist"
        )


def _require_ignored_parent(root: Path, parent: Path) -> Path:
    resolved_root = root.resolve()
    resolved_parent = parent.resolve()
    try:
        relative = resolved_parent.relative_to(resolved_root).as_posix()
    except ValueError as error:
        raise ReleaseBuildContextError(
            "scheduler build context must remain inside the project"
        ) from error
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=resolved_root,
        check=False,
        capture_output=True,
    )
    if ignored.returncode != 0:
        raise ReleaseBuildContextError("scheduler build-context root is not Git ignored")
    return resolved_parent


def _safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise ReleaseBuildContextError("Git archive contains an unsafe path")
    return path


def _extract_controlled_archive(
    archive_path: Path,
    destination: Path,
    expected_names: tuple[str, ...],
) -> None:
    expected = set(expected_names)
    extracted: set[str] = set()
    try:
        archive = tarfile.open(archive_path, mode="r:")
    except (OSError, tarfile.TarError) as error:
        raise ReleaseBuildContextError("Git archive is unreadable") from error
    with archive:
        for member in archive.getmembers():
            relative = _safe_member_path(member.name)
            if member.isdir():
                (destination / relative).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile() or member.name not in expected:
                raise ReleaseBuildContextError(
                    "Git archive contains a non-controlled or unsupported member"
                )
            source = archive.extractfile(member)
            if source is None:
                raise ReleaseBuildContextError("Git archive member cannot be read")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("xb") as handle:
                shutil.copyfileobj(source, handle)
            target.chmod(member.mode & 0o777)
            extracted.add(member.name)
    if extracted != expected:
        missing = sorted(expected - extracted)
        raise ReleaseBuildContextError(
            "Git archive controlled-file set is incomplete: " + ", ".join(missing)
        )


def _archive_revision(
    root: Path,
    revision: str,
    names: tuple[str, ...],
    archive_path: Path,
) -> None:
    _git(
        root,
        "archive",
        "--format=tar",
        f"--output={archive_path}",
        revision,
        "--",
        *names,
    )


@contextmanager
def prepare_scheduler_build_context(
    *,
    project_root: Path,
    context_parent: Path,
) -> Iterator[SchedulerBuildContext]:
    """Yield an ignored context containing only controlled files from pushed HEAD."""
    root = project_root.resolve()
    parent = _require_ignored_parent(root, context_parent)
    revision = _require_pushed_clean_controlled_tree(root)
    expected_names = _controlled_git_names(root, revision)
    run_root = parent / uuid.uuid4().hex
    context = run_root / "context"
    archive_path = run_root / "controlled-source.tar"
    manifest_path = run_root / "source-manifest.json"
    try:
        context.mkdir(parents=True, exist_ok=False)
        _archive_revision(root, revision, expected_names, archive_path)
        _extract_controlled_archive(archive_path, context, expected_names)
        actual_names = tuple(controlled_tree_names(context))
        if actual_names != expected_names:
            raise ReleaseBuildContextError(
                "isolated scheduler context differs from the controlled Git tree"
            )
        document = write_release_manifest(manifest_path, root=context)
        if _require_pushed_clean_controlled_tree(root) != revision:
            raise ReleaseBuildContextError("scheduler release source changed during archiving")
        yield SchedulerBuildContext(
            path=context,
            git_head=revision,
            code_snapshot_sha256=str(document["code_snapshot_sha256"]),
            file_count=int(document["file_count"]),
        )
    finally:
        shutil.rmtree(run_root, ignore_errors=True)
