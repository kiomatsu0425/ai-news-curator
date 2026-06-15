from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            feed_url TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            jp_title TEXT,
            jp_summary TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            score REAL NOT NULL DEFAULT 0,
            selected_date TEXT,
            selected_rank INTEGER,
            selected_bucket TEXT,
            opened_at TEXT
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES articles(id)
        );

        CREATE TABLE IF NOT EXISTS source_weights (
            source TEXT PRIMARY KEY,
            weight REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tag_weights (
            tag TEXT PRIMARY KEY,
            weight REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_articles_selected
            ON articles(selected_date, selected_rank);
        CREATE INDEX IF NOT EXISTS idx_articles_source
            ON articles(source);
        CREATE INDEX IF NOT EXISTS idx_feedback_article
            ON feedback(article_id);
        """
    )


def upsert_article(conn: sqlite3.Connection, article: dict) -> int:
    conn.execute(
        """
        INSERT INTO articles (
            url, source, feed_url, title, summary, content, published_at, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            summary = COALESCE(excluded.summary, articles.summary),
            content = COALESCE(excluded.content, articles.content),
            published_at = COALESCE(excluded.published_at, articles.published_at),
            fetched_at = excluded.fetched_at
        """,
        (
            article["url"],
            article["source"],
            article["feed_url"],
            article["title"],
            article.get("summary"),
            article.get("content"),
            article.get("published_at"),
            utc_now(),
        ),
    )
    row = conn.execute("SELECT id FROM articles WHERE url = ?", (article["url"],)).fetchone()
    return int(row["id"])


def save_summary(conn: sqlite3.Connection, article_id: int, jp_title: str, jp_summary: str, tags: list[str]) -> None:
    conn.execute(
        """
        UPDATE articles
        SET jp_title = ?, jp_summary = ?, tags_json = ?
        WHERE id = ?
        """,
        (jp_title, jp_summary, json.dumps(tags, ensure_ascii=False), article_id),
    )


def record_feedback(conn: sqlite3.Connection, article_id: int, action: str) -> None:
    now = utc_now()
    conn.execute(
        "INSERT INTO feedback (article_id, action, created_at) VALUES (?, ?, ?)",
        (article_id, action, now),
    )
    if action == "opened":
        conn.execute("UPDATE articles SET opened_at = COALESCE(opened_at, ?) WHERE id = ?", (now, article_id))

    article = conn.execute("SELECT source, tags_json FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not article:
        return

    delta = {"opened": 1.0, "useful": 0.65, "bad": -1.1, "later": 0.15}.get(action, 0)
    if not delta:
        return

    conn.execute(
        """
        INSERT INTO source_weights (source, weight, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            weight = source_weights.weight + excluded.weight,
            updated_at = excluded.updated_at
        """,
        (article["source"], delta, now),
    )

    for tag in json.loads(article["tags_json"] or "[]"):
        conn.execute(
            """
            INSERT INTO tag_weights (tag, weight, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(tag) DO UPDATE SET
                weight = tag_weights.weight + excluded.weight,
                updated_at = excluded.updated_at
            """,
            (tag, delta, now),
        )

