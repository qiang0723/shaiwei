"""Discover and immutably retrieve official index launch, rules and adjustment materials."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from shaiwei.config import PROJECT_ROOT
from tools.official_index_lineage.contract import load_protocol, sha256_file, tool_snapshot_sha256
from tools.official_index_lineage.source_store import ContentAddressedFetcher, SourceRecord

ARCHIVE_URL = "https://www.sse.com.cn/market/sseindex/diclosure/"
PAGE_RE = re.compile(r"/market/sseindex/diclosure/c/c_(\d{8})_\d+\.shtml$")
ATTACHMENT_RE = re.compile(r"\.(?:pdf|xlsx?|docx?|wps)(?:$|[?#])", re.IGNORECASE)
DEFAULT_PROTOCOL = PROJECT_ROOT / "config" / "m2_star200_v1.yaml"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _archive_page_url(page_number: int) -> str:
    if page_number == 1:
        return ARCHIVE_URL + "s_list.shtml"
    return ARCHIVE_URL + f"s_list_{page_number}.shtml"


def announcement_rows(content: bytes) -> list[dict[str, str]]:
    soup = BeautifulSoup(content, "html.parser")
    rows: dict[str, dict[str, str]] = {}
    for anchor in soup.select('a[href*="/market/sseindex/diclosure/c/c_"]'):
        href = urljoin(ARCHIVE_URL, anchor.get("href", ""))
        match = PAGE_RE.search(urlparse(href).path)
        if match:
            rows[href] = {
                "announcement_date": match.group(1),
                "source_url": href,
                "title": html.unescape(anchor.get("title") or anchor.get_text(" ", strip=True)),
            }
    return [rows[url] for url in sorted(rows)]


def is_candidate(row: dict[str, str], explicit_urls: set[str]) -> bool:
    if row["source_url"] in explicit_urls:
        return True
    title = row["title"]
    adjustment = "调整" in title and ("样本" in title or "定期调整结果" in title)
    temporary_adjustment = "临时调整" in title
    return title.startswith("关于") and (adjustment or temporary_adjustment)


def attachment_urls(content: bytes, parent_url: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    urls = {
        urljoin(parent_url, anchor.get("href", ""))
        for anchor in soup.select("a[href]")
        if ATTACHMENT_RE.search(urljoin(parent_url, anchor.get("href", "")))
    }
    return sorted(urls)


def _explicit_assets(policy: dict[str, object]) -> dict[str, tuple[str, str | None]]:
    launch = str(policy["launch_announcement_url"])
    revision = str(policy["methodology_revision_url"])
    return {
        str(policy["launch_methodology_url"]): ("launch_methodology", launch),
        str(policy["launch_members_url"]): ("launch_members", launch),
        str(policy["current_methodology_url"]): ("current_methodology", revision),
    }


def discover(
    fetcher: ContentAddressedFetcher,
    protocol: dict[str, object],
    protocol_path: Path,
) -> dict[str, object]:
    policy = protocol["official_source_policy"]
    start = str(policy["discovery_start_date"]).replace("-", "")
    end = str(policy["discovery_end_date"]).replace("-", "")
    explicit_pages = {
        str(policy["launch_announcement_url"]),
        str(policy["methodology_revision_url"]),
    }
    archive_records: list[SourceRecord] = []
    boundaries = []
    candidates: dict[str, dict[str, str]] = {}
    crossed_start = False
    for page_number in range(1, 100):
        url = _archive_page_url(page_number)
        content, record = fetcher.fetch(url, purpose="official_archive_listing")
        archive_records.append(record)
        rows = announcement_rows(content)
        dates = [row["announcement_date"] for row in rows]
        boundaries.append(
            {
                "page_number": page_number,
                "source_url": url,
                "source_file_sha256": record.source_file_sha256,
                "entry_count": len(rows),
                "newest_announcement_date": max(dates) if dates else None,
                "oldest_announcement_date": min(dates) if dates else None,
            }
        )
        for row in rows:
            if start <= row["announcement_date"] <= end and is_candidate(row, explicit_pages):
                candidates[row["source_url"]] = row
        if dates and max(dates) < start:
            crossed_start = True
            break
    if not crossed_start:
        raise RuntimeError("official archive scan did not cross the launch boundary")

    launch = str(policy["launch_announcement_url"])
    revision = str(policy["methodology_revision_url"])
    candidates.setdefault(
        launch,
        {"announcement_date": "20240721", "source_url": launch, "title": "launch_publication"},
    )
    candidates.setdefault(
        revision,
        {"announcement_date": "20250226", "source_url": revision, "title": "methodology_revision"},
    )
    page_records: list[SourceRecord] = []
    attachment_records: dict[str, SourceRecord] = {}
    explicit_assets = _explicit_assets(policy)
    for url, row in sorted(candidates.items(), key=lambda item: (item[1]["announcement_date"], item[0])):
        purpose = (
            "launch_publication"
            if url == launch
            else "methodology_revision"
            if url == revision
            else "adjustment_candidate"
        )
        content, record = fetcher.fetch(url, purpose=purpose, title=row["title"])
        page_records.append(record)
        for asset_url in attachment_urls(content, url):
            asset_purpose, parent = explicit_assets.get(asset_url, ("official_attachment", url))
            _, attachment = fetcher.fetch(
                asset_url,
                purpose=asset_purpose,
                parent_url=parent,
                title=row["title"],
            )
            attachment_records[asset_url] = attachment
    for asset_url, (purpose, parent) in explicit_assets.items():
        if asset_url not in attachment_records:
            _, attachment = fetcher.fetch(asset_url, purpose=purpose, parent_url=parent)
            attachment_records[asset_url] = attachment

    payload = {
        "schema_version": "official-index-discovery-v1",
        "protocol_schema_version": protocol["schema_version"],
        "protocol_config_sha256": sha256_file(protocol_path),
        "protocol_document_sha256": protocol["protocol_sha256"],
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "index_code": protocol["identity"]["index_code"],
        "source_cutoff_date": protocol["identity"]["source_cutoff_date"],
        "archive_boundary_crossed": crossed_start,
        "archive_page_count": len(archive_records),
        "candidate_announcement_count": len(page_records),
        "attachment_count": len(attachment_records),
        "archive_boundaries": boundaries,
        "classified_pages": [
            {
                "announcement_date": row["announcement_date"],
                "source_url": url,
                "title": row["title"],
                "purpose": (
                    "launch_publication"
                    if url == launch
                    else "methodology_revision"
                    if url == revision
                    else "adjustment_candidate"
                ),
            }
            for url, row in sorted(candidates.items())
        ],
        "sources": [
            asdict(record)
            for record in [*archive_records, *page_records, *attachment_records.values()]
        ],
    }
    rendered = _canonical_json(payload)
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    report_path = fetcher.raw_root.parent / f"official-discovery-{digest[:12]}.json"
    if report_path.exists() and report_path.read_text(encoding="utf-8") != rendered:
        raise RuntimeError("immutable discovery report differs")
    if not report_path.exists():
        report_path.write_text(rendered, encoding="utf-8")
    payload["report_path"] = str(report_path.relative_to(PROJECT_ROOT))
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else PROJECT_ROOT / args.protocol
    protocol = load_protocol(protocol_path)
    payload = discover(ContentAddressedFetcher(protocol), protocol, protocol_path)
    print(
        json.dumps(
            {
                "archive_page_count": payload["archive_page_count"],
                "candidate_announcement_count": payload["candidate_announcement_count"],
                "attachment_count": payload["attachment_count"],
                "report_path": payload["report_path"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
