"""Read-only R2D metadata adapter; no Compose parsing or candidate container runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from shaiwei import release
from shaiwei import r2d_release_guard as guard
from shaiwei.release_guard import SchedulerIdentity
from shaiwei.release_metadata import confined, latest_forward, sha256
from shaiwei.storage.runtime_mount_contract import validate_scheduler_mounts


@dataclass(frozen=True)
class ObservedScheduler(SchedulerIdentity):
    restart_count: int = -1


class SecureEnvironment(guard.R2DEnvironment):
    def __init__(self, project_root: Path, compose_project: str):
        self.root = project_root
        self.compose_project = compose_project

    def release_hashes(self) -> tuple[str, str]:
        return (
            sha256(confined(self.root, ".release/scheduler_state.json")),
            sha256(confined(self.root, "logs/releases/scheduler_releases.jsonl")),
        )

    def latest_forward(self, account_id: str) -> dict[str, str]:
        return latest_forward(account_id, self.root)

    def verify_candidate(self, image: str) -> dict[str, str]:
        # Runtime content was verified by the hash-bound immutable fixture.
        # A preflight must not instantiate another candidate container.
        return release._image_metadata(image)

    def running_scheduler(self) -> ObservedScheduler:
        ids = self._run([
            "docker", "ps", "--no-trunc", "--filter",
            f"label=com.docker.compose.project={self.compose_project}",
            "--filter", "label=com.docker.compose.service=scheduler",
            "--format", "{{.ID}}",
        ]).stdout.split()
        if len(ids) != 1:
            raise guard.base.GuardError("scheduler container identity is ambiguous")
        # Only explicitly named metadata is requested, never Config.Env.
        result = self._run([
            "docker", "inspect", "--format",
            '{"id":{{json .Id}},"image":{{json .Image}},'
            '"running":{{json .State.Running}},"restart":{{json .RestartCount}},'
            '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"missing"{{end}},'
            '"readonly":{{json .HostConfig.ReadonlyRootfs}},"mounts":{{json .Mounts}}}',
            ids[0],
        ])
        value = json.loads(result.stdout)
        if value["id"] != ids[0] or value["running"] is not True:
            raise guard.base.GuardError("scheduler is not the observed running container")
        mounts = value["mounts"]
        destinations = validate_scheduler_mounts(mounts, lock_required=True)
        if len(mounts) != 4:
            raise guard.base.GuardError("scheduler requires exactly four mounts")
        for mount in mounts:
            if mount["Type"] == "bind":
                relative = {"data": "data", "ledger": "ledger", "logs": "logs"}[
                    mount["Destination"].rsplit("/", 1)[-1]
                ]
                if mount.get("Source") != str(confined(self.root, relative)):
                    raise guard.base.GuardError("scheduler bind source differs from project")
        metadata = release._image_metadata(value["image"])
        return ObservedScheduler(
            container_id=value["id"], image_id=value["image"],
            health=value["health"], read_only_rootfs=value["readonly"],
            restart_count=value["restart"],
            code_snapshot_sha256=metadata["code_snapshot_sha256"],
            git_head=metadata["git_head"],
            mount_destinations=tuple(destinations),
            lock_authority=metadata.get("lock_authority", "legacy-bind-flock-v0"),
        )

    def start_once(self, before_mutation):
        return release.start_current(before_mutation=before_mutation,
                                     compose_project=self.compose_project)
