from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def fetch_page_text(url: str, timeout: int = 12) -> str:
    try:
        res = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "personal-news-curator/0.1"},
        )
        res.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    return text[:6000]


def fetch_feed(feed: dict, max_items: int = 20, include_page_text: bool = True) -> list[dict]:
    parsed = feedparser.parse(feed["url"])
    articles: list[dict] = []
    for entry in parsed.entries[:max_items]:
        url = entry.get("link")
        title = entry.get("title")
        if not url or not title:
            continue

        summary = clean_html(entry.get("summary") or entry.get("description"))
        content = ""
        if entry.get("content"):
            content = clean_html(entry.content[0].get("value"))
        if include_page_text and len(content) < 800:
            content = fetch_page_text(url) or content

        articles.append(
            {
                "url": url,
                "source": feed["name"],
                "feed_url": feed["url"],
                "title": clean_html(title),
                "summary": summary,
                "content": content[:6000],
                "published_at": parse_date(entry.get("published") or entry.get("updated")),
            }
        )
    return articles

