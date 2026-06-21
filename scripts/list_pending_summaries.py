from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_curator.postgres_store import pending_articles


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Print articles that need Codex Automation summaries.")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    items = pending_articles(limit=args.limit)
    print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
