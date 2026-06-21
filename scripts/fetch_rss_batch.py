from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_curator.config import load_feeds, load_settings
from news_curator.fetcher import fetch_feed
from news_curator.postgres_store import upsert_raw_articles


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Fetch RSS articles into Neon Postgres without LLM calls.")
    parser.add_argument("--max-items-per-feed", type=int, default=12)
    args = parser.parse_args()

    settings = load_settings()
    feeds = load_feeds(settings.feeds_path)
    articles = []
    for feed in feeds:
        articles.extend(fetch_feed(feed, max_items=args.max_items_per_feed, include_page_text=False))

    stats = upsert_raw_articles(articles)
    print(stats)


if __name__ == "__main__":
    main()
