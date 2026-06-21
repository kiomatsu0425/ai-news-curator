from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_curator.postgres_store import record_feedback, save_summary, upsert_raw_articles


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Import existing data/news_items.json into Neon Postgres once.")
    parser.add_argument("--path", default="data/news_items.json")
    args = parser.parse_args()

    path = Path(args.path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    stats = upsert_raw_articles(articles)
    summaries = 0
    for article in articles:
        if article.get("jp_title") and article.get("jp_summary"):
            save_summary(
                article["url"],
                article["jp_title"],
                article["jp_summary"],
                article.get("tags") or [],
            )
            summaries += 1
    feedback_count = 0
    for url, actions in (data.get("feedback") or {}).items():
        for action in actions:
            name = action.get("action") if isinstance(action, dict) else None
            if name in {"opened", "useful", "bad", "later"}:
                record_feedback(url, name)
                feedback_count += 1

    print(json.dumps({**stats, "summaries": summaries, "feedback": feedback_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
