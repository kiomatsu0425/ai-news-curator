from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_curator.postgres_store import save_summary


def parse_tags(value: str) -> list[str]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    if not isinstance(loaded, list):
        raise argparse.ArgumentTypeError("--tags-json must be a JSON array or comma-separated text.")
    return [str(tag).strip() for tag in loaded if str(tag).strip()]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Save one summarized article into Neon Postgres.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--jp-title", required=True)
    parser.add_argument("--jp-summary", required=True)
    parser.add_argument("--tags-json", required=True, type=parse_tags)
    args = parser.parse_args()

    save_summary(args.url, args.jp_title, args.jp_summary, args.tags_json)
    print(json.dumps({"updated": args.url}, ensure_ascii=False))


if __name__ == "__main__":
    main()
