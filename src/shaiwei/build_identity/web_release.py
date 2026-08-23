"""Command-line entrypoint for the local Web component release gate."""

from __future__ import annotations

import argparse
import json
from typing import Mapping

from shaiwei.build_identity.web_release_build import (
    build_candidate,
    load_and_verify_candidate,
)
from shaiwei.build_identity.web_release_deploy import (
    promote_with_rollback_drill,
    start_deployed_release,
    verify_deployed_release,
)
from shaiwei.build_identity.web_release_successor import prepare_successor_candidate


def _summary(action: str, document: Mapping[str, object]) -> dict[str, object]:
    attestation = document.get("attestation")
    if isinstance(attestation, dict):
        images = attestation.get("images")
        image_rows = images if isinstance(images, list) else []
        return {
            "action": action,
            "status": "PASS",
            "candidate_sha256": document.get("candidate_sha256"),
            "release_identity_sha256": attestation.get("attestation_sha256"),
            "image_ids": {
                str(row.get("role")): row.get("image_id")
                for row in image_rows
                if isinstance(row, dict)
            },
            "production_authorization": "none",
        }
    current_images = document.get("current_images")
    if isinstance(current_images, dict):
        return {
            "action": action,
            "status": "PASS",
            "candidate_sha256": document.get("current_candidate_sha256"),
            "release_identity_sha256": document.get("current_release_identity_sha256"),
            "image_ids": {
                str(role): row.get("image_id")
                for role, row in current_images.items()
                if isinstance(row, dict)
            },
            "rollback_drill_passed": document.get("rollback_drill_passed"),
            "production_authorization": "none",
        }
    allowed = {
        "status",
        "archived_candidate_sha256",
        "candidate_sha256",
        "release_identity_sha256",
        "container_ids",
        "scheduler_identity_unchanged",
        "rollback_drill_passed",
        "production_authorization",
        "local_read_only_deployment",
    }
    return {"action": action, **{key: value for key, value in document.items() if key in allowed}}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare-successor",
            "build",
            "verify-candidate",
            "promote",
            "start",
            "status",
        ),
    )
    return parser


def main() -> int:
    action = _parser().parse_args().action
    if action == "prepare-successor":
        result = prepare_successor_candidate()
    elif action == "build":
        result = build_candidate()
    elif action == "verify-candidate":
        result = load_and_verify_candidate()
    elif action == "promote":
        result = promote_with_rollback_drill()
    elif action == "start":
        result = start_deployed_release()
    else:
        result = verify_deployed_release()
    print(json.dumps(_summary(action, result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
