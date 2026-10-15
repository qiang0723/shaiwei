"""Fixture composition root; deliberately not registered as a live scheduler or CLI."""

from datetime import datetime
from pathlib import Path
from typing import Callable

from shaiwei.r2d_candidate_contract import CandidatePlan, TickResult, require
from shaiwei.r2d_candidate_metadata import FixtureMetadataSpec, OfflineMetadataReader
from shaiwei.r2d_candidate_runner import BusinessPort, INGRESSES, run_offline_tick
from shaiwei.r2d_candidate_store import OfflineStageStore


def run_fixture_candidate(
    *, ingress: str, directory: Path, plan: CandidatePlan, metadata_spec: FixtureMetadataSpec,
    business_factory: Callable[[], BusinessPort], clock: Callable[[], datetime],
) -> TickResult:
    """Open an existing fixture journal and read fixed-name, white-listed metadata."""
    require(ingress in INGRESSES, "UNKNOWN_INGRESS")
    require(ingress == "scheduler", "STANDALONE_BUSINESS_INGRESS_DENIED")
    store = OfflineStageStore(directory, plan)  # Never implicitly create a claim database.
    metadata = OfflineMetadataReader(directory, metadata_spec, store)
    return run_offline_tick(
        ingress=ingress, plan=plan, store=store, metadata=metadata,
        business_factory=business_factory, clock=clock,
    )
