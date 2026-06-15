from __future__ import annotations

from .config import load_feeds, load_settings
from .db import connect, init_db, save_summary, upsert_article
from .fetcher import fetch_feed
from .ranker import score_articles, select_daily
from .summarizer import summarize_article


def run_daily(max_items_per_feed: int = 12) -> dict[str, int]:
    settings = load_settings()
    feeds = load_feeds(settings.feeds_path)
    feed_weights = {feed["name"]: float(feed.get("base_weight", 0.8)) for feed in feeds}

    fetched = 0
    summarized = 0
    with connect(settings.db_path) as conn:
        init_db(conn)
        for feed in feeds:
            for article in fetch_feed(feed, max_items=max_items_per_feed):
                article_id = upsert_article(conn, article)
                fetched += 1
                row = conn.execute(
                    "SELECT jp_title FROM articles WHERE id = ?",
                    (article_id,),
                ).fetchone()
                if row and row["jp_title"]:
                    continue
                result = summarize_article(article, settings.openai_api_key, settings.openai_model)
                save_summary(conn, article_id, result["jp_title"], result["jp_summary"], result["tags"])
                summarized += 1
        score_articles(conn, feed_weights)
        selected = select_daily(conn, settings.daily_limit, settings.exploration_count)

    return {"fetched": fetched, "summarized": summarized, "selected": len(selected)}

