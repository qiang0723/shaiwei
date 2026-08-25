"""Versioned scheduler persistence-mount contract for release verification."""

from __future__ import annotations


LOCK_VOLUME_NAME = "shaiwei_runtime_locks_v1"
LOCK_VOLUME_DESTINATION = "/run/shaiwei-locks"
LOCK_AUTHORITY = "docker-named-volume-v1"


class RuntimeMountContractError(RuntimeError):
    pass


def validate_scheduler_mounts(
    mounts: object,
    *,
    lock_required: bool,
) -> list[str]:
    """Return sorted destinations after exact type/source/RW validation."""
    if not isinstance(mounts, list):
        raise RuntimeMountContractError("scheduler mounts are missing")
    destinations = {
        str(mount.get("Destination")): mount
        for mount in mounts
        if isinstance(mount, dict)
    }
    base_mounts = {
        "/workspace/data": ("bind", None),
        "/workspace/ledger": ("bind", None),
        "/workspace/logs": ("bind", None),
    }
    lock_mount = {LOCK_VOLUME_DESTINATION: ("volume", LOCK_VOLUME_NAME)}
    allowed_destinations = [set(base_mounts) | set(lock_mount)]
    if not lock_required:
        allowed_destinations.append(set(base_mounts))
    if set(destinations) not in allowed_destinations:
        raise RuntimeMountContractError(
            "scheduler mounts differ from the explicit production allowlist"
        )
    if any(mount.get("RW") is not True for mount in destinations.values()):
        raise RuntimeMountContractError("scheduler persistence mounts must remain writable")
    expected = {**base_mounts, **(lock_mount if LOCK_VOLUME_DESTINATION in destinations else {})}
    for destination, (mount_type, source) in expected.items():
        mount = destinations[destination]
        if mount.get("Type") != mount_type:
            raise RuntimeMountContractError(
                "scheduler mount type differs from the production contract"
            )
        if source is not None and mount.get("Name", mount.get("Source")) != source:
            raise RuntimeMountContractError(
                "scheduler lock volume identity differs from the production contract"
            )
    if "/workspace" in destinations:
        raise RuntimeMountContractError("scheduler still mounts a host directory over /workspace")
    return sorted(destinations)
