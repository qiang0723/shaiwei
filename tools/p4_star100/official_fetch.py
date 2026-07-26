"""Discover and immutably retrieve official Star100 lineage materials."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import yaml

from shaiwei.config import PROJECT_ROOT
from tools.p2_star50_v2.official_fetch import CurlFetcher, OfficialFetchError
from tools.p4_star100.contract import PROTOCOL_PATH, sha256_file, tool_snapshot_sha256

ARCHIVE_URL = "https://www.sse.com.cn/market/sseindex/diclosure/"


def _archive_page_url(page_number: int) -> str:
    if page_number == 1:
        return ARCHIVE_URL + "s_list.shtml"
    return ARCHIVE_URL + f"s_list_{page_number}.shtml"


def _announcement_rows(content: bytes) -> list[dict[str, str]]:
    soup = BeautifulSoup(content, "html.parser")
    rows: dict[str, dict[str, str]] = {}
    for anchor in soup.select('a[href*="/market/sseindex/diclosure/c/c_"]'):
        href = urljoin(ARCHIVE_URL, anchor.get("href", ""))
        name = Path(urlparse(href).path).name
        parts = name.split("_")
        if len(parts) < 3 or len(parts[1]) != 8 or not parts[1].isdigit():
            continue
        rows[href] = {
            "announcement_date": parts[1],
            "source_url": href,
            "title": html.unescape(anchor.get("title") or anchor.get_text(" ", strip=True)),
        }
    return [rows[url] for url in sorted(rows)]


def _is_candidate(row: dict[str, str], protocol: dict[str, object]) -> bool:
    url = row["source_url"]
    title = row["title"]
    explicit_urls = {
        str(protocol["official_source_policy"]["launch_announcement_url"]),
        str(protocol["official_source_policy"]["methodology_revision_url"]),
    }
    if url in explicit_urls:
        return True
    adjustment = "调整" in title and ("样本" in title or "定期调整结果" in title)
    temporary = "临时调整" in title
    return title.startswith("关于") and (adjustment or temporary)


def _attachment_urls(content: bytes, parent_url: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    suffixes = (".pdf", ".xlsx", ".xls", ".docx", ".wps")
    urls = set()
    for anchor in soup.select("a[href]"):
        href = urljoin(parent_url, anchor.get("href", ""))
        if urlparse(href).path.lower().endswith(suffixes):
            urls.add(href)
    return sorted(urls)


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def discover(fetcher: CurlFetcher, protocol: dict[str, object]) -> dict[str, object]:
    start = str(protocol["official_source_policy"]["discovery_start_date"]).replace("-", "")
    end = str(protocol["official_source_policy"]["discovery_end_date"]).replace("-", "")
    archive_records = []
    archive_boundaries: list[dict[str, object]] = []
    candidate_rows: dict[str, dict[str, str]] = {}
    crossed_start = False
    for page_number in range(1, 100):
        url = _archive_page_url(page_number)
        content, record = fetcher.fetch(url, purpose="official_archive_listing")
        archive_records.append(record)
        rows = _announcement_rows(content)
        dates = [row["announcement_date"] for row in rows]
        archive_boundaries.append(
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
            if start <= row["announcement_date"] <= end and _is_candidate(row, protocol):
                candidate_rows[row["source_url"]] = row
        if dates and max(dates) < start:
            crossed_start = True
            break
    else:
        raise OfficialFetchError("official archive discovery exceeded bounded page limit")
    if not crossed_start:
        raise OfficialFetchError("official archive scan did not cross the launch boundary")

    explicit = (
        ("launch_announcement_url", "launch_publication"),
        ("methodology_revision_url", "methodology_revision"),
    )
    for key, purpose in explicit:
        url = str(protocol["official_source_policy"][key])
        candidate_rows.setdefault(
            url,
            {
                "announcement_date": "20230721" if purpose == "launch_publication" else "20250226",
                "source_url": url,
                "title": purpose,
            },
        )

    page_records = []
    attachment_records = []
    classified_pages = []
    launch_url = str(protocol["official_source_policy"]["launch_announcement_url"])
    revision_url = str(protocol["official_source_policy"]["methodology_revision_url"])
    for url, row in sorted(candidate_rows.items(), key=lambda item: (item[1]["announcement_date"], item[0])):
        purpose = (
            "launch_publication"
            if url == launch_url
            else "methodology_revision"
            if url == revision_url
            else "adjustment_candidate"
        )
        content, record = fetcher.fetch(url, purpose=purpose, title=row["title"])
        page_records.append(record)
        attachments = _attachment_urls(content, url)
        classified_pages.append(
            {
                "announcement_date": row["announcement_date"],
                "source_url": url,
                "title": row["title"],
                "purpose": purpose,
                "attachment_count": len(attachments),
            }
        )
        for attachment_url in attachments:
            _, attachment = fetcher.fetch(
                attachment_url,
                purpose="official_attachment",
                parent_url=url,
                title=row["title"],
            )
            attachment_records.append(attachment)

    current_methodology_url = str(protocol["official_source_policy"]["current_methodology_url"])
    if current_methodology_url not in {record.source_url for record in attachment_records}:
        _, record = fetcher.fetch(
            current_methodology_url,
            purpose="official_attachment",
            parent_url=revision_url,
            title="current_methodology_v1_1",
        )
        attachment_records.append(record)

    payload = {
        "schema_version": "p4-star100-official-discovery-v1",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "source_cutoff_date": protocol["identity"]["source_cutoff_date"],
        "archive_scan_crossed_launch_boundary": crossed_start,
        "archive_page_count": len(archive_records),
        "candidate_page_count": len(page_records),
        "attachment_count": len(attachment_records),
        "archive_boundaries": archive_boundaries,
        "classified_pages": classified_pages,
        "sources": [asdict(record) for record in [*archive_records, *page_records, *attachment_records]],
    }
    rendered = _canonical_json(payload)
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    report_path = fetcher.raw_root.parent / f"official-discovery-{digest[:12]}.json"
    if report_path.exists() and report_path.read_text(encoding="utf-8") != rendered:
        raise OfficialFetchError("immutable discovery report differs")
    report_path.write_text(rendered, encoding="utf-8")
    return {**payload, "discovery_report": str(report_path.relative_to(PROJECT_ROOT))}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else PROJECT_ROOT / args.protocol
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    policy = protocol["official_source_policy"]
    raw_root = PROJECT_ROOT / str(protocol["identity"]["raw_source_root"])
    fetcher = CurlFetcher(
        raw_root,
        allowed_domains=set(policy["primary_domains"]),
        interval=float(policy["minimum_request_interval_seconds"]),
        attempts=int(policy["maximum_attempts"]),
        retry_base=float(policy["retry_base_seconds"]),
        maximum_bytes=int(policy["maximum_file_bytes"]),
    )
    payload = discover(fetcher, protocol)
    print(
        json.dumps(
            {
                "status": "OFFICIAL_DISCOVERY_CAPTURED",
                "archive_page_count": payload["archive_page_count"],
                "candidate_page_count": payload["candidate_page_count"],
                "attachment_count": payload["attachment_count"],
                "discovery_report": payload["discovery_report"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
