from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings

_RECENCY_MARKERS = (
    "最近",
    "最新",
    "目前",
    "现在",
    "今天",
    "昨日",
    "昨天",
    "刚刚",
    "近期",
    "这周",
    "本周",
    "本月",
    "今年",
    "新闻",
    "进展",
    "动态",
    "发生了什么",
)
_FACT_MARKERS = ("谁", "何时", "什么时候", "是否", "有没有", "为什么", "怎么回事")
_TRUSTED_DOMAINS = (
    "gov.cn",
    "sec.gov",
    "courtlistener.com",
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "caixin.com",
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_RELATIVE_DATE_RE = re.compile(r"^(\d+)\s*(分钟|小时|天)前$")


@dataclass(frozen=True)
class WebFact:
    id: str
    title: str
    summary: str
    source_url: str
    source_domain: str
    published_at: str | None
    retrieved_at: str
    trust: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def needs_web_context(text: str, *, now: datetime | None = None) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    current = now or datetime.now(UTC)
    has_recency = any(marker in normalized for marker in _RECENCY_MARKERS)
    has_current_year = str(current.year) in normalized
    asks_fact = any(marker in normalized for marker in _FACT_MARKERS)
    return has_recency or (has_current_year and asks_fact)


def _clean(value: str | None, *, limit: int) -> str:
    text = html.unescape(_TAG_RE.sub(" ", value or ""))
    return _SPACE_RE.sub(" ", text).strip()[:limit]


def _published_at(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _trust_for(domain: str) -> str:
    if any(domain == item or domain.endswith(f".{item}") for item in _TRUSTED_DOMAINS):
        return "high"
    return "standard"


def parse_bing_news_rss(payload: str, *, limit: int) -> list[WebFact]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return []
    retrieved_at = datetime.now(UTC).isoformat()
    facts: list[WebFact] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = _clean(item.findtext("title"), limit=220)
        summary = _clean(item.findtext("description"), limit=800)
        source_url = _clean(item.findtext("link"), limit=2000)
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.netloc or not title:
            continue
        fingerprint = hashlib.sha256(f"{title}|{source_url}".encode()).hexdigest()[:20]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        domain = parsed.netloc.lower().removeprefix("www.")
        facts.append(
            WebFact(
                id=f"web-{fingerprint}",
                title=title,
                summary=summary,
                source_url=source_url,
                source_domain=domain,
                published_at=_published_at(item.findtext("pubDate")),
                retrieved_at=retrieved_at,
                trust=_trust_for(domain),
            )
        )
        if len(facts) >= limit:
            break
    return facts


def _class_has(attributes: dict[str, str], name: str) -> bool:
    return name in attributes.get("class", "").split()


class _SoNewsParser(HTMLParser):
    """Extract the compact news cards embedded in 360 Search results."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.capture: str | None = None

    def _finish(self) -> None:
        if self.current and self.current.get("title") and self.current.get("source_url"):
            self.items.append(self.current)
        self.current = None
        self.capture = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "a" and _class_has(attributes, "mh-news-title"):
            self._finish()
            self.current = {
                "source_url": attributes.get("data-mdurl", ""),
                "title": "",
                "summary": "",
                "published": "",
            }
            self.capture = "title"
        elif self.current and tag == "p" and _class_has(attributes, "mh-news-desc"):
            self.capture = "summary"
        elif self.current and tag == "span" and _class_has(attributes, "mh-pdate"):
            self.capture = "published"

    def handle_endtag(self, tag: str) -> None:
        if (tag == "a" and self.capture == "title") or (
            tag == "p" and self.capture == "summary"
        ) or (tag == "span" and self.capture == "published"):
            self.capture = None

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture:
            self.current[self.capture] += data

    def close(self) -> None:
        super().close()
        self._finish()


def _relative_published_at(value: str, *, now: datetime) -> str | None:
    from datetime import timedelta

    normalized = _SPACE_RE.sub("", value)
    match = _RELATIVE_DATE_RE.match(normalized)
    if not match:
        return _published_at(value)
    amount = int(match.group(1))
    unit = match.group(2)
    delta = {
        "分钟": timedelta(minutes=amount),
        "小时": timedelta(hours=amount),
        "天": timedelta(days=amount),
    }[unit]
    return (now - delta).astimezone(UTC).isoformat()


def parse_so_news_html(
    payload: str,
    *,
    persona_name: str,
    limit: int,
    now: datetime | None = None,
) -> list[WebFact]:
    parser = _SoNewsParser()
    try:
        parser.feed(payload)
        parser.close()
    except (ValueError, AssertionError):
        return []
    retrieved = now or datetime.now(UTC)
    retrieved_at = retrieved.isoformat()
    facts: list[WebFact] = []
    seen: set[str] = set()
    for item in parser.items:
        title = _clean(item.get("title"), limit=220)
        summary = _clean(item.get("summary"), limit=800)
        source_url = _clean(item.get("source_url"), limit=2000)
        parsed = urlparse(source_url)
        # Search cards occasionally contain popular but unrelated news. Requiring
        # the target name keeps those snippets out of the model context.
        if persona_name not in f"{title} {summary}":
            continue
        if parsed.scheme != "https" or not parsed.netloc or not title:
            continue
        fingerprint = hashlib.sha256(f"{title}|{source_url}".encode()).hexdigest()[:20]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        domain = parsed.netloc.lower().removeprefix("www.")
        facts.append(
            WebFact(
                id=f"web-{fingerprint}",
                title=title,
                summary=summary,
                source_url=source_url,
                source_domain=domain,
                published_at=_relative_published_at(item.get("published", ""), now=retrieved),
                retrieved_at=retrieved_at,
                trust=_trust_for(domain),
            )
        )
        if len(facts) >= limit:
            break
    return facts


async def search_current_facts(persona_name: str, user_text: str) -> list[WebFact]:
    settings = get_settings()
    if not settings.web_search_enabled or not needs_web_context(user_text):
        return []
    # Natural dialogue often contains pronouns and long instructions that search
    # engines handle poorly. Keep the entity exact and retain only high-signal
    # acronyms/years from the question for a stable recency query.
    query_hints = re.findall(r"20\d{2}", user_text)
    query = " ".join([persona_name, *query_hints[:3], "最近", "公开事件"])
    so_url = settings.web_search_base_url.rstrip("/")
    providers = (
        [("so_search", so_url), ("bing_rss", "https://cn.bing.com/search")]
        if settings.web_search_provider == "so_search"
        else [("bing_rss", so_url), ("so_search", "https://www.so.com/s")]
    )
    async with httpx.AsyncClient(
        timeout=settings.web_search_timeout_seconds,
        follow_redirects=True,
        # Deployment traffic should not inherit an unrelated shell proxy. This
        # also avoids CONNECT failures seen in local production-like testing.
        trust_env=False,
    ) as client:
        for provider, base_url in providers:
            parameters = (
                {"q": query}
                if provider == "so_search"
                else {"q": query, "format": "rss", "setlang": "zh-hans"}
            )
            url = f"{base_url}?{urlencode(parameters)}"
            try:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; XianxianXinyu/1.0)"},
                )
                response.raise_for_status()
            except (httpx.HTTPError, ValueError):
                continue
            facts = (
                parse_so_news_html(
                    response.text,
                    persona_name=persona_name,
                    limit=settings.web_search_max_results,
                )
                if provider == "so_search"
                else [
                    fact
                    for fact in parse_bing_news_rss(
                        response.text,
                        limit=settings.web_search_max_results * 2,
                    )
                    if persona_name in f"{fact.title} {fact.summary}"
                ][: settings.web_search_max_results]
            )
            if facts:
                return facts
    return []
