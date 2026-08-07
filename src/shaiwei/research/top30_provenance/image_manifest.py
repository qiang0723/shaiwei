"""Write the content-addressed manifest embedded in R3 thin images."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from shaiwei.research.top30_provenance.contract import code_bundle_identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = code_bundle_identity()
    document = {
        "schema_version": "m6-top30-numeric-provenance-image-manifest-v1",
        "role": os.environ.get("SHAIWEI_M6_TOP30_PROVENANCE_ROLE", ""),
        "git_commit": os.environ.get("SHAIWEI_M6_TOP30_PROVENANCE_GIT_HEAD", ""),
        "base_image_id": os.environ.get("SHAIWEI_M6_TOP30_PROVENANCE_BASE_IMAGE_ID", ""),
        "code_bundle_sha256": bundle["sha256"],
        "code_bundle_file_count": bundle["file_count"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
