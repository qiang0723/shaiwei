"""Collect a secret-free runtime and package fingerprint inside an existing base image."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
from typing import Any

import numpy as np

from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.top30_provenance.contract import (
    Protocol,
    ReleaseScope,
    runtime_identity,
    write_once_document,
)


PACKAGES = (
    "numpy",
    "pandas",
    "pyarrow",
    "scipy",
    "lightgbm",
    "pyqlib",
    "joblib",
)
SOURCE_PATHS = (
    "/workspace/src/shaiwei/backtest/strategy.py",
    "/workspace/src/shaiwei/research/model_attribution/effect_artifacts.py",
    "/workspace/src/shaiwei/research/model_attribution/effect_execution.py",
    "/workspace/src/shaiwei/research/model_attribution/effect_run.py",
    "/workspace/src/shaiwei/research/topk_conversion/execution.py",
)
THREAD_ENV_NAMES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def _distribution_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def _numpy_build() -> dict[str, Any]:
    config = getattr(np.__config__, "CONFIG", {})
    dependencies = config.get("Build Dependencies", {}) if isinstance(config, dict) else {}
    machine = config.get("Machine Information", {}) if isinstance(config, dict) else {}
    simd = config.get("SIMD Extensions", {}) if isinstance(config, dict) else {}
    safe_dependencies = {}
    for key in ("blas", "lapack"):
        row = dependencies.get(key, {}) if isinstance(dependencies, dict) else {}
        safe_dependencies[key] = {
            field: row.get(field)
            for field in ("name", "found", "version", "detection method", "openblas configuration")
        }
    return {"dependencies": safe_dependencies, "machine": machine, "simd": simd}


def _source_identity() -> dict[str, dict[str, Any]]:
    result = {}
    for raw in SOURCE_PATHS:
        path = Path(raw)
        result[path.as_posix()] = (
            {"present": True, "sha256": sha256_file(path), "size": path.stat().st_size}
            if path.is_file()
            else {"present": False}
        )
    return result


def probe(role: str, protocol_path: Path, release_path: Path, output: Path) -> dict[str, Any]:
    protocol = Protocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    runtime = runtime_identity(release, role)
    libc_name, libc_version = platform.libc_ver()
    document = {
        "schema_version": "m6-top30-numeric-provenance-image-probe-v1",
        "provenance_scope_sha256": release.sha256,
        "runtime_identity": runtime,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "libc_name": libc_name,
            "libc_version": libc_version,
        },
        "distributions": _distribution_versions(),
        "numpy_build": _numpy_build(),
        "thread_environment_names_present": sorted(name for name in THREAD_ENV_NAMES if name in os.environ),
        "source_identity": _source_identity(),
        "network_authorized": False,
        "qlib_mounted": False,
        "top30_backtest_count": 0,
        "top20_backtest_count": 0,
    }
    digest, reused = write_once_document(output, document)
    return {"sha256": digest, "reused": reused, "role": role}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("original", "failed"), required=True)
    parser.add_argument("--protocol", dest="protocol_path", type=Path, required=True)
    parser.add_argument("--release", dest="release_path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
