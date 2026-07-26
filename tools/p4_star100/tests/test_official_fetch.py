from __future__ import annotations

from tools.p4_star100.official_fetch import _announcement_rows, _is_candidate


def _protocol() -> dict[str, object]:
    return {
        "official_source_policy": {
            "launch_announcement_url": "https://www.sse.com.cn/market/sseindex/diclosure/c/c_20230721_5724116.shtml",
            "methodology_revision_url": "https://www.sse.com.cn/market/sseindex/diclosure/c/c_20250226_10772987.shtml",
        }
    }


def test_archive_rows_are_normalized() -> None:
    rows = _announcement_rows(
        b'<a href="/market/sseindex/diclosure/c/c_20250530_1.shtml" title="x">x</a>'
    )
    assert rows == [
        {
            "announcement_date": "20250530",
            "source_url": "https://www.sse.com.cn/market/sseindex/diclosure/c/c_20250530_1.shtml",
            "title": "x",
        }
    ]


def test_candidate_selection_is_broad_but_bounded_to_index_notices() -> None:
    protocol = _protocol()
    assert _is_candidate(
        {
            "source_url": protocol["official_source_policy"]["launch_announcement_url"],
            "title": "关于发布上证科创板100指数的公告",
        },
        protocol,
    )
    assert _is_candidate(
        {
            "source_url": "https://www.sse.com.cn/market/sseindex/diclosure/c/c_20260529_1.shtml",
            "title": "关于上证50、上证180、上证380等指数定期调整结果的公告",
        },
        protocol,
    )
    assert not _is_candidate(
        {
            "source_url": "https://www.sse.com.cn/market/sseindex/diclosure/c/c_20260529_2.shtml",
            "title": "关于发布某行业指数的公告",
        },
        protocol,
    )
