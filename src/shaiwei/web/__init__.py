"""Read-only Web 1.0 query and transport boundary."""

from shaiwei.web.operations import OperationsBundle, build_operations_snapshot
from shaiwei.web.query import SnapshotBundle, WebQueryError, build_snapshot

__all__ = [
    "OperationsBundle",
    "SnapshotBundle",
    "WebQueryError",
    "build_operations_snapshot",
    "build_snapshot",
]
