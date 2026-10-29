"""TP-F-1 user blind review (addendum A1): a numbers-free packet and a strictly parsed verbatim ruling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from shaiwei.research.tp_f_1.contract import TPF1Error

PACKET_FIELDS = ("candidate_id", "canonical_expression", "economic_rationale")
VETO_LABELS = {"不是这个机制": "NOT_THIS_MECHANISM", "换皮重复": "DISGUISED_DUPLICATE"}
_ITEM = re.compile(r"^(?P<cid>[0-9a-f]{12})\s*(?P<verb>保留|否决（(?P<reason>不是这个机制|换皮重复)）)$")


def blind_packet(scope_sha256: str, candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Only id, canonical expression and rationale; no market-derived number, statistic or direction."""
    if not candidates:
        raise TPF1Error("TP-F-1 blind review has no qualified candidate")
    items = [{key: str(candidate[key]) for key in PACKET_FIELDS} for candidate in candidates]
    if len({item["candidate_id"] for item in items}) != len(items):
        raise TPF1Error("TP-F-1 blind review candidate ids are not unique")
    return {"schema_version": "tp-f-1-blind-review-packet-v1", "scope_sha256": scope_sha256, "candidates": items,
            "allowed_veto_reasons": list(VETO_LABELS.values()), "contains_market_numbers": False}


def ruling_template(packet: Mapping[str, Any]) -> str:
    """Grammar the user writes in their own words; the tool never fills in a decision."""
    ids = [item["candidate_id"] for item in packet["candidates"]]
    return (f"盲评 TP-F-1 scope {packet['scope_sha256']}：" + "；".join(f"{cid} 保留|否决（不是这个机制|换皮重复）" for cid in ids) + "。")


def parse_ruling(packet: Mapping[str, Any], text: str) -> dict[str, str]:
    prefix = f"盲评 TP-F-1 scope {packet['scope_sha256']}："
    if not text.startswith(prefix) or not text.endswith("。"):
        raise TPF1Error("TP-F-1 blind review ruling does not follow the frozen grammar")
    decisions: dict[str, str] = {}
    for part in text[len(prefix):-1].split("；"):
        match = _ITEM.fullmatch(part.strip())
        if match is None:
            raise TPF1Error(f"TP-F-1 blind review item is not parseable: {part.strip()[:40]}")
        cid = match["cid"]
        if cid in decisions:
            raise TPF1Error(f"TP-F-1 blind review names a candidate twice: {cid}")
        decisions[cid] = "RETAIN" if match["verb"] == "保留" else VETO_LABELS[match["reason"]]
    expected = {item["candidate_id"] for item in packet["candidates"]}
    if set(decisions) != expected:
        raise TPF1Error("TP-F-1 blind review must decide every packet candidate exactly once")
    return decisions


def record_ruling(path: Path, packet: Mapping[str, Any], text: str) -> dict[str, Any]:
    decisions = parse_ruling(packet, text)
    document = {"schema_version": "tp-f-1-blind-review-ruling-v1", "scope_sha256": packet["scope_sha256"],
                "verbatim_user_text": text, "decisions": decisions,
                "retained": sorted(cid for cid, value in decisions.items() if value == "RETAIN")}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise TPF1Error("TP-F-1 blind review ruling is already recorded") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return document
