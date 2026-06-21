from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

from .config import load_settings


BROKEN_TEXT_PATTERNS = (
    "???",
    "????",
    "・ｽ",
    "遯ｶ",
    "繝ｻ・ｽ",
    "驕ｯ・ｶ",
)
JAPANESE_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
FEEDBACK_DELTAS = {"opened": 1.0, "useful": 0.65, "bad": -1.1, "later": 0.15}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_database_url() -> str:
    database_url = load_settings().database_url
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set a Neon Postgres connection string "
            "in .env, Streamlit Secrets, and GitHub Actions Secrets."
        )
    return database_url


@contextmanager
def connect() -> Iterator[Any]:
    database_url = require_database_url()
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("psycopg is required. Install dependencies with pip install -r requirements.txt.") from exc

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        yield conn
        conn.commit()


def init_db(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            feed_url TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            published_at TIMESTAMPTZ,
            fetched_at TIMESTAMPTZ NOT NULL,
            jp_title TEXT,
            jp_summary TEXT,
            tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            score DOUBLE PRECISION NOT NULL DEFAULT 0,
            selected_date DATE,
            selected_rank INTEGER,
            selected_bucket TEXT,
            opened_at TIMESTAMPTZ
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id BIGSERIAL PRIMARY KEY,
            article_url TEXT NOT NULL REFERENCES articles(url) ON DELETE CASCADE,
            action TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_weights (
            source TEXT PRIMARY KEY,
            weight DOUBLE PRECISION NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tag_weights (
            tag TEXT PRIMARY KEY,
            weight DOUBLE PRECISION NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_selected ON articles(selected_date, selected_rank)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_article ON feedback(article_url)")


def ensure_db() -> None:
    with connect() as conn:
        init_db(conn)


def _to_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    return value


def _article_row(row: dict[str, Any]) -> dict[str, Any]:
    article = dict(row)
    tags = article.pop("tags_json", []) or []
    article["tags"] = tags if isinstance(tags, list) else json.loads(tags)
    for key in ("published_at", "fetched_at", "opened_at"):
        if article.get(key) is not None:
            article[key] = article[key].isoformat()
    if article.get("selected_date") is not None:
        article["selected_date"] = article["selected_date"].isoformat()
    return article


def looks_mojibake(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if any(pattern in value for pattern in BROKEN_TEXT_PATTERNS):
        return True
    question_count = value.count("?")
    replacement_count = value.count("\ufffd")
    if replacement_count > 0:
        return True
    return question_count >= 5 and question_count / max(len(value), 1) > 0.08


def has_broken_japanese(text: str | None) -> bool:
    if not text:
        return False
    if looks_mojibake(text):
        return True
    return "?" in text and not JAPANESE_CHAR_RE.search(text)


def article_needs_summary(article: dict[str, Any]) -> bool:
    jp_title = article.get("jp_title")
    jp_summary = article.get("jp_summary")
    return (
        not jp_title
        or not jp_summary
        or has_broken_japanese(jp_title)
        or has_broken_japanese(jp_summary)
    )


def upsert_raw_articles(articles: list[dict[str, Any]]) -> dict[str, int]:
    inserted = 0
    updated = 0
    now = utc_now()
    with connect() as conn:
        init_db(conn)
        for article in articles:
            content = (article.get("content") or article.get("summary") or "")[:1200]
            before = conn.execute("SELECT 1 FROM articles WHERE url = %s", (article["url"],)).fetchone()
            conn.execute(
                """
                INSERT INTO articles (
                    url, source, feed_url, title, summary, content, published_at, fetched_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    source = EXCLUDED.source,
                    feed_url = EXCLUDED.feed_url,
                    title = EXCLUDED.title,
                    summary = COALESCE(EXCLUDED.summary, articles.summary),
                    content = COALESCE(EXCLUDED.content, articles.content),
                    published_at = COALESCE(EXCLUDED.published_at, articles.published_at),
                    fetched_at = EXCLUDED.fetched_at
                """,
                (
                    article["url"],
                    article["source"],
                    article["feed_url"],
                    article["title"],
                    article.get("summary"),
                    content,
                    _to_timestamp(article.get("published_at")),
                    now,
                ),
            )
            if before:
                updated += 1
            else:
                inserted += 1
    return {"inserted": inserted, "updated": updated, "total": article_count()}


def article_count() -> int:
    with connect() as conn:
        init_db(conn)
        row = conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()
    return int(row["count"])


def store_stats() -> dict[str, Any]:
    with connect() as conn:
        init_db(conn)
        article_total = conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"]
        feedback_total = conn.execute("SELECT COUNT(*) AS count FROM feedback").fetchone()["count"]
        fetched_at = conn.execute("SELECT MAX(fetched_at) AS value FROM articles").fetchone()["value"]
    return {
        "articles": int(article_total),
        "feedback": int(feedback_total),
        "generated_at": fetched_at.isoformat() if fetched_at else None,
    }


def pending_articles(limit: int = 12) -> list[dict[str, Any]]:
    with connect() as conn:
        init_db(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM articles
            ORDER BY published_at DESC NULLS LAST, fetched_at DESC
            """
        ).fetchall()
    pending = []
    for row in rows:
        article = _article_row(row)
        if article_needs_summary(article):
            pending.append(article)
        if len(pending) >= limit:
            break
    return pending


def save_summary(url: str, jp_title: str, jp_summary: str, tags: list[str]) -> None:
    clean_tags = [tag.strip() for tag in tags if tag.strip()]
    with connect() as conn:
        init_db(conn)
        conn.execute(
            """
            UPDATE articles
            SET jp_title = %s,
                jp_summary = %s,
                tags_json = %s::jsonb,
                selected_date = NULL,
                selected_rank = NULL,
                selected_bucket = NULL
            WHERE url = %s
            """,
            (jp_title, jp_summary, json.dumps(clean_tags, ensure_ascii=False), url),
        )


def reset_mojibake_summaries() -> dict[str, int]:
    with connect() as conn:
        init_db(conn)
        rows = conn.execute("SELECT url, jp_title, jp_summary, tags_json FROM articles").fetchall()
        reset_urls = [
            row["url"]
            for row in rows
            if article_needs_summary(_article_row(row))
            and (row.get("jp_title") or row.get("jp_summary") or row.get("tags_json"))
        ]
        if reset_urls:
            conn.execute(
                """
                UPDATE articles
                SET jp_title = NULL,
                    jp_summary = NULL,
                    tags_json = '[]'::jsonb,
                    selected_date = NULL,
                    selected_rank = NULL,
                    selected_bucket = NULL
                WHERE url = ANY(%s)
                """,
                (reset_urls,),
            )
        total = conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"]
    return {"reset": len(reset_urls), "total": int(total)}


def _age_days(published_at: str | None) -> float:
    if not published_at:
        return 4.0
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 4.0
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)


def _freshness_score(published_at: str | None) -> float:
    return 2.0 * math.exp(-_age_days(published_at) / 7.0)


def _weights(conn: Any) -> tuple[dict[str, float], dict[str, float]]:
    source_weights = {
        row["source"]: float(row["weight"])
        for row in conn.execute("SELECT source, weight FROM source_weights").fetchall()
    }
    tag_weights = {
        row["tag"]: float(row["weight"])
        for row in conn.execute("SELECT tag, weight FROM tag_weights").fetchall()
    }
    return source_weights, tag_weights


def select_daily_articles(
    feed_weights: dict[str, float],
    limit: int = 12,
    exploration_count: int = 2,
    max_per_source: int = 3,
) -> list[dict[str, Any]]:
    today_key = date.today().isoformat()
    with connect() as conn:
        init_db(conn)
        existing = conn.execute(
            """
            SELECT *
            FROM articles
            WHERE selected_date = %s
            ORDER BY selected_rank ASC
            """,
            (today_key,),
        ).fetchall()
        if existing:
            return [_article_row(row) for row in existing]

        source_weights, tag_weights = _weights(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM articles
            WHERE jp_title IS NOT NULL
              AND jp_summary IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM feedback f
                  WHERE f.article_url = articles.url
                    AND f.action IN ('useful', 'bad')
              )
            ORDER BY published_at DESC NULLS LAST, fetched_at DESC
            LIMIT 200
            """
        ).fetchall()

        candidates: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            article = _article_row(row)
            if article_needs_summary(article):
                continue
            tags = article.get("tags") or []
            tag_pref = sum(tag_weights.get(tag, 0.0) for tag in tags) / max(len(tags), 1)
            score = (
                _freshness_score(article.get("published_at"))
                + feed_weights.get(article["source"], 0.8)
                + source_weights.get(article["source"], 0.0)
                + tag_pref
                + random.uniform(0, 0.05)
            )
            article["score"] = score
            candidates.append((score, article))

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected: list[dict[str, Any]] = []
        source_counts: Counter[str] = Counter()
        ranked_target = max(0, limit - exploration_count)

        for _, article in candidates:
            if len(selected) >= ranked_target:
                break
            if source_counts[article["source"]] >= max_per_source:
                continue
            selected.append(article)
            source_counts[article["source"]] += 1

        selected_urls = {article["url"] for article in selected}
        exploration_pool = [
            article
            for _, article in candidates
            if article["url"] not in selected_urls and source_counts[article["source"]] < max_per_source
        ]
        random.shuffle(exploration_pool)
        for article in exploration_pool[:exploration_count]:
            selected.append(article)
            source_counts[article["source"]] += 1

        for rank, article in enumerate(selected, start=1):
            bucket = "exploration" if rank > ranked_target else "ranked"
            article["selected_date"] = today_key
            article["selected_rank"] = rank
            article["selected_bucket"] = bucket
            conn.execute(
                """
                UPDATE articles
                SET selected_date = %s,
                    selected_rank = %s,
                    selected_bucket = %s,
                    score = %s
                WHERE url = %s
                """,
                (today_key, rank, bucket, article["score"], article["url"]),
            )

    return selected


def record_feedback(url: str, action: str) -> None:
    if action not in FEEDBACK_DELTAS:
        raise ValueError(f"Unsupported feedback action: {action}")

    now = utc_now()
    delta = FEEDBACK_DELTAS[action]
    with connect() as conn:
        init_db(conn)
        article = conn.execute("SELECT source, tags_json FROM articles WHERE url = %s", (url,)).fetchone()
        if not article:
            return

        conn.execute(
            "INSERT INTO feedback (article_url, action, created_at) VALUES (%s, %s, %s)",
            (url, action, now),
        )
        if action == "opened":
            conn.execute("UPDATE articles SET opened_at = COALESCE(opened_at, %s) WHERE url = %s", (now, url))

        conn.execute(
            """
            INSERT INTO source_weights (source, weight, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (source) DO UPDATE SET
                weight = source_weights.weight + EXCLUDED.weight,
                updated_at = EXCLUDED.updated_at
            """,
            (article["source"], delta, now),
        )

        tags = article.get("tags_json") or []
        if isinstance(tags, str):
            tags = json.loads(tags)
        for tag in tags:
            conn.execute(
                """
                INSERT INTO tag_weights (tag, weight, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (tag) DO UPDATE SET
                    weight = tag_weights.weight + EXCLUDED.weight,
                    updated_at = EXCLUDED.updated_at
                """,
                (tag, delta, now),
            )
