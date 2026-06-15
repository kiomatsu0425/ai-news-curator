from __future__ import annotations

import json
import math
import random
from collections import Counter
from datetime import date, datetime, timezone
from sqlite3 import Connection, Row


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


def score_articles(conn: Connection, feed_weights: dict[str, float]) -> None:
    source_weights = {
        row["source"]: row["weight"]
        for row in conn.execute("SELECT source, weight FROM source_weights").fetchall()
    }
    tag_weights = {
        row["tag"]: row["weight"]
        for row in conn.execute("SELECT tag, weight FROM tag_weights").fetchall()
    }
    rows = conn.execute("SELECT id, source, published_at, tags_json FROM articles").fetchall()
    for row in rows:
        tags = json.loads(row["tags_json"] or "[]")
        tag_pref = sum(tag_weights.get(tag, 0.0) for tag in tags) / max(len(tags), 1)
        score = (
            _freshness_score(row["published_at"])
            + feed_weights.get(row["source"], 0.8)
            + source_weights.get(row["source"], 0.0)
            + tag_pref
            + random.uniform(0, 0.05)
        )
        conn.execute("UPDATE articles SET score = ? WHERE id = ?", (score, row["id"]))


def _without_feedback_where() -> str:
    return """
        NOT EXISTS (
            SELECT 1 FROM feedback f
            WHERE f.article_id = articles.id
              AND f.action IN ('useful', 'bad')
        )
    """


def select_daily(
    conn: Connection,
    limit: int,
    exploration_count: int,
    max_per_source: int = 3,
    today: date | None = None,
) -> list[Row]:
    today = today or date.today()
    today_key = today.isoformat()
    existing = conn.execute(
        """
        SELECT * FROM articles
        WHERE selected_date = ?
        ORDER BY selected_rank ASC
        """,
        (today_key,),
    ).fetchall()
    if existing:
        return existing

    ranked = conn.execute(
        f"""
        SELECT * FROM articles
        WHERE jp_title IS NOT NULL
          AND {_without_feedback_where()}
        ORDER BY score DESC
        LIMIT 200
        """
    ).fetchall()

    selected: list[Row] = []
    source_counts: Counter[str] = Counter()
    for row in ranked:
        if len(selected) >= max(0, limit - exploration_count):
            break
        if source_counts[row["source"]] >= max_per_source:
            continue
        selected.append(row)
        source_counts[row["source"]] += 1

    selected_ids = {row["id"] for row in selected}
    exploration_pool = [
        row for row in ranked
        if row["id"] not in selected_ids and source_counts[row["source"]] < max_per_source
    ]
    random.shuffle(exploration_pool)
    for row in exploration_pool[:exploration_count]:
        selected.append(row)
        source_counts[row["source"]] += 1

    for rank, row in enumerate(selected, start=1):
        bucket = "exploration" if rank > max(0, limit - exploration_count) else "ranked"
        conn.execute(
            """
            UPDATE articles
            SET selected_date = ?, selected_rank = ?, selected_bucket = ?
            WHERE id = ?
            """,
            (today_key, rank, bucket, row["id"]),
        )

    return conn.execute(
        "SELECT * FROM articles WHERE selected_date = ? ORDER BY selected_rank ASC",
        (today_key,),
    ).fetchall()

