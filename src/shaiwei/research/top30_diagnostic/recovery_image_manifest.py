"""Build the content-addressed wrapper manifest for Top30 recovery images."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from shaiwei.research.top30_diagnostic.contract import code_bundle_identity
from shaiwei.research.top30_diagnostic.exact import DiagnosticError


def build_manifest() -> dict[str, str]:
    values = {
        "git_commit": os.getenv("SHAIWEI_M6_TOP30_RECOVERY_GIT_HEAD", ""),
        "role": os.getenv("SHAIWEI_M6_TOP30_RECOVERY_ROLE", ""),
        "base_image_id": os.getenv("SHAIWEI_M6_TOP30_RECOVERY_BASE_IMAGE_ID", ""),
        "code_bundle_sha256": code_bundle_identity()["sha256"],
    }
    if len(values["git_commit"]) != 40 or values["role"] not in {"original", "current"}:
        raise DiagnosticError("Top30 recovery image build identity differs")
    if not values["base_image_id"].startswith("sha256:"):
        raise DiagnosticError("Top30 recovery base image identity differs")
    return {"schema_version": "m6-top30-diagnostic-recovery-image-manifest-v2", **values}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_manifest(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
