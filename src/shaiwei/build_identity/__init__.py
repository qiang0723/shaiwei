"""Versioned component build identity contracts."""

from shaiwei.build_identity.registry import (
    BuildAssetClass,
    BuildComponent,
    BuildIdentityError,
    BuildRegistry,
    load_build_registry,
)
from shaiwei.build_identity.release import (
    verify_component_release_attestation,
    verify_sealed_component_identity,
)

__all__ = [
    "BuildAssetClass",
    "BuildComponent",
    "BuildIdentityError",
    "BuildRegistry",
    "load_build_registry",
    "verify_component_release_attestation",
    "verify_sealed_component_identity",
]
