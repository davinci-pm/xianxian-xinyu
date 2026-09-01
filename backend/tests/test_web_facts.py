from datetime import UTC, datetime

from app.services.web_facts import needs_web_context, parse_bing_news_rss, parse_so_news_html


def test_needs_web_context_routes_only_recency_or_current_year_questions() -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    assert needs_web_context("孙宇晨最近发生了什么？", now=now)
    assert needs_web_context("2026 年他有没有新的公开动态？", now=now)
    assert not needs_web_context("他为什么进入加密行业？", now=now)


def test_parse_bing_news_rss_sanitizes_and_deduplicates() -> None:
    payload = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>监管机构公布新进展</title>
        <link>https://www.sec.gov/example</link>
        <description><![CDATA[<b>公开文件</b> 已发布。]]></description>
        <pubDate>Mon, 31 Aug 2026 08:00:00 GMT</pubDate>
      </item>
      <item>
        <title>监管机构公布新进展</title>
        <link>https://www.sec.gov/example</link>
      </item>
      <item><title>不安全链接</title><link>http://example.com/a</link></item>
    </channel></rss>"""

    facts = parse_bing_news_rss(payload, limit=5)

    assert len(facts) == 1
    assert facts[0].summary == "公开文件 已发布。"
    assert facts[0].source_domain == "sec.gov"
    assert facts[0].trust == "high"
    assert facts[0].published_at == "2026-08-31T08:00:00+00:00"


def test_parse_so_news_html_keeps_direct_relevant_sources_only() -> None:
    payload = """
    <a data-mdurl="https://example.com/relevant" class="mh-news-title g-ellipsis">
      孙宇晨最新公开回应
    </a>
    <p class="mh-news-desc">公开文件已发布，涉及 <em>孙宇晨</em>。</p>
    <span class="mh-pdate">3天前</span>
    <a data-mdurl="https://example.com/unrelated" class="mh-news-title">另一条新闻</a>
    <p class="mh-news-desc">与目标人物无关。</p>
    <span class="mh-pdate">1小时前</span>
    <a data-mdurl="http://example.com/unsafe" class="mh-news-title">孙宇晨不安全链接</a>
    """

    facts = parse_so_news_html(
        payload,
        persona_name="孙宇晨",
        limit=5,
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert len(facts) == 1
    assert facts[0].title == "孙宇晨最新公开回应"
    assert facts[0].summary == "公开文件已发布，涉及 孙宇晨。"
    assert facts[0].source_url == "https://example.com/relevant"
    assert facts[0].published_at == "2026-08-29T00:00:00+00:00"
