from __future__ import annotations

import json
import math
import random
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .db import utc_now


DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "news_items.json"


def load_store(path: Path = DEFAULT_STORE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "articles": [], "feedback": {}}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("generated_at", None)
    data.setdefault("articles", [])
    data.setdefault("feedback", {})
    return data


def looks_mojibake(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    question_count = value.count("?")
    replacement_count = value.count("\ufffd")
    return replacement_count > 0 or (question_count >= 5 and question_count / max(len(value), 1) > 0.08)


def save_store(data: dict[str, Any], path: Path = DEFAULT_STORE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["generated_at"] = utc_now()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def upsert_raw_articles(articles: list[dict[str, Any]], path: Path = DEFAULT_STORE_PATH) -> dict[str, int]:
    data = load_store(path)
    by_url = {article["url"]: article for article in data["articles"]}
    inserted = 0
    updated = 0

    for article in articles:
        url = article["url"]
        compact_content = (article.get("content") or article.get("summary") or "")[:1200]
        if url in by_url:
            current = by_url[url]
            for key in ("source", "feed_url", "title", "summary", "content", "published_at"):
                if key == "content":
                    current[key] = compact_content
                elif article.get(key):
                    current[key] = article[key]
            updated += 1
        else:
            article = {
                **article,
                "content": compact_content,
                "jp_title": None,
                "jp_summary": None,
                "tags": [],
                "fetched_at": utc_now(),
                "selected_date": None,
                "selected_rank": None,
                "selected_bucket": None,
            }
            data["articles"].append(article)
            inserted += 1

    save_store(data, path)
    return {"inserted": inserted, "updated": updated, "total": len(data["articles"])}


def pending_articles(limit: int = 12, path: Path = DEFAULT_STORE_PATH) -> list[dict[str, Any]]:
    data = load_store(path)
    pending = [
        article for article in data["articles"]
        if (
            not article.get("jp_title")
            or not article.get("jp_summary")
            or looks_mojibake(article.get("jp_title"))
            or looks_mojibake(article.get("jp_summary"))
        )
    ]
    return sorted(pending, key=lambda a: a.get("published_at") or "", reverse=True)[:limit]


def reset_mojibake_summaries(path: Path = DEFAULT_STORE_PATH) -> dict[str, int]:
    data = load_store(path)
    reset_count = 0
    for article in data["articles"]:
        if looks_mojibake(article.get("jp_title")) or looks_mojibake(article.get("jp_summary")):
            article["jp_title"] = None
            article["jp_summary"] = None
            article["tags"] = []
            article["selected_date"] = None
            article["selected_rank"] = None
            article["selected_bucket"] = None
            reset_count += 1

    if reset_count:
        save_store(data, path)

    return {"reset": reset_count, "total": len(data["articles"])}


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


def _feedback_weights(data: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    source_weights: dict[str, float] = {}
    tag_weights: dict[str, float] = {}
    article_by_url = {article["url"]: article for article in data["articles"]}

    for url, actions in data.get("feedback", {}).items():
        article = article_by_url.get(url)
        if not article:
            continue
        source = article["source"]
        for action in actions:
            delta = {"opened": 1.0, "useful": 0.65, "bad": -1.1, "later": 0.15}.get(action.get("action"), 0)
            source_weights[source] = source_weights.get(source, 0.0) + delta
            for tag in article.get("tags") or []:
                tag_weights[tag] = tag_weights.get(tag, 0.0) + delta

    return source_weights, tag_weights


def select_daily_articles(
    feed_weights: dict[str, float],
    limit: int = 12,
    exploration_count: int = 2,
    max_per_source: int = 3,
    path: Path = DEFAULT_STORE_PATH,
) -> list[dict[str, Any]]:
    data = load_store(path)
    today_key = date.today().isoformat()
    existing = [
        article for article in data["articles"]
        if article.get("selected_date") == today_key and article.get("jp_title")
    ]
    if existing:
        return sorted(existing, key=lambda a: a.get("selected_rank") or 999)

    source_weights, tag_weights = _feedback_weights(data)
    candidates = []
    for article in data["articles"]:
        if (
            not article.get("jp_title")
            or not article.get("jp_summary")
            or looks_mojibake(article.get("jp_title"))
            or looks_mojibake(article.get("jp_summary"))
        ):
            continue
        feedback_actions = [a["action"] for a in data.get("feedback", {}).get(article["url"], [])]
        if "useful" in feedback_actions or "bad" in feedback_actions:
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
        article for _, article in candidates
        if article["url"] not in selected_urls and source_counts[article["source"]] < max_per_source
    ]
    random.shuffle(exploration_pool)
    selected.extend(exploration_pool[:exploration_count])

    for rank, article in enumerate(selected, start=1):
        article["selected_date"] = today_key
        article["selected_rank"] = rank
        article["selected_bucket"] = "exploration" if rank > ranked_target else "ranked"

    save_store(data, path)
    return selected


def record_feedback(url: str, action: str, path: Path = DEFAULT_STORE_PATH) -> None:
    data = load_store(path)
    data.setdefault("feedback", {}).setdefault(url, []).append({"action": action, "created_at": utc_now()})
    save_store(data, path)
