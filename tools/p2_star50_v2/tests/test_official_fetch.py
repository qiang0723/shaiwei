from __future__ import annotations

from tools.p2_star50_v2.official_fetch import (
    _announcement_rows,
    _archive_page_url,
    _attachment_urls,
    _is_candidate,
)


def test_archive_page_one_has_special_name() -> None:
    assert _archive_page_url(1).endswith("/s_list.shtml")
    assert _archive_page_url(2).endswith("/s_list_2.shtml")


def test_discovery_parses_and_filters_official_rows() -> None:
    content = b"""
    <a href="/market/sseindex/diclosure/c/c_20260227_10810439.shtml"
       title="&#20851;&#20110;&#31185;&#21019;50&#31561;&#25351;&#25968;&#19968;&#23395;&#24230;&#23450;&#26399;&#35843;&#25972;&#32467;&#26524;&#30340;&#20844;&#21578;">x</a>
    <a href="/market/sseindex/diclosure/c/c_20260220_1.shtml" title="unrelated">y</a>
    """
    rows = _announcement_rows(content)
    assert rows[0]["announcement_date"] == "20260220"
    assert rows[1]["announcement_date"] == "20260227"
    assert not _is_candidate(rows[0])
    assert _is_candidate(rows[1])


def test_general_quarterly_title_is_candidate() -> None:
    row = {
        "title": "关于上证50、上证180、上证380等指数定期调整结果的公告",
        "announcement_date": "20260529",
        "source_url": "https://www.sse.com.cn/example",
    }
    assert _is_candidate(row)


def test_official_news_summary_and_nonmembership_page_are_not_candidates() -> None:
    assert not _is_candidate(
        {
            "title": "上交所及中证指数调整沪深300、上证50、科创50和中证500等指数样本",
            "announcement_date": "20210528",
            "source_url": "https://www.sse.com.cn/example",
        }
    )
    assert not _is_candidate(
        {
            "title": "关于变更上证科创板50成份指数成交金额（量）计算方式的公告",
            "announcement_date": "20250418",
            "source_url": "https://www.sse.com.cn/example",
        }
    )


def test_legacy_general_adjustment_page_is_candidate() -> None:
    assert _is_candidate(
        {
            "title": "关于调整上证50、上证180、上证380等指数样本的公告",
            "announcement_date": "20201127",
            "source_url": "https://www.sse.com.cn/example",
        }
    )


def test_attachments_are_official_absolute_and_deduplicated() -> None:
    parent = "https://www.sse.com.cn/market/sseindex/diclosure/c/c_1.shtml"
    content = b'<a href="100/files/a.pdf">a</a><a href="100/files/a.pdf">a2</a>'
    assert _attachment_urls(content, parent) == [
        "https://www.sse.com.cn/market/sseindex/diclosure/c/100/files/a.pdf"
    ]


def test_official_wps_attachment_is_discovered() -> None:
    parent = "https://www.sse.com.cn/market/sseindex/diclosure/c/c_1.shtml"
    content = b'<a href="100/files/member-list.wps">members</a>'
    assert _attachment_urls(content, parent) == [
        "https://www.sse.com.cn/market/sseindex/diclosure/c/100/files/member-list.wps"
    ]
