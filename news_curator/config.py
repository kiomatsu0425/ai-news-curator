from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FEEDS_PATH = ROOT / "feeds.json"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    feeds_path: Path
    openai_api_key: str | None
    openai_model: str
    daily_limit: int
    exploration_count: int


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    db_path = Path(os.getenv("NEWS_DB_PATH", "data/news_curator.sqlite3"))
    feeds_path = Path(os.getenv("NEWS_FEEDS_PATH", str(DEFAULT_FEEDS_PATH)))
    return Settings(
        db_path=db_path if db_path.is_absolute() else ROOT / db_path,
        feeds_path=feeds_path if feeds_path.is_absolute() else ROOT / feeds_path,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        daily_limit=int(os.getenv("NEWS_DAILY_LIMIT", "12")),
        exploration_count=int(os.getenv("NEWS_EXPLORATION_COUNT", "2")),
    )


def load_feeds(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
