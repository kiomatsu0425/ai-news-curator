from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FEEDS_PATH = ROOT / "feeds.json"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    feeds_path: Path
    app_password: str | None
    daily_limit: int
    exploration_count: int


def _read_streamlit_secret(key: str) -> Any | None:
    try:
        import streamlit as st

        return st.secrets.get(key)
    except Exception:
        return None


def _setting(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is not None:
        return value

    secret = _read_streamlit_secret(key)
    if secret is not None:
        return str(secret)

    return default


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    db_path = Path(_setting("NEWS_DB_PATH", "data/news_curator.sqlite3") or "data/news_curator.sqlite3")
    feeds_path = Path(_setting("NEWS_FEEDS_PATH", str(DEFAULT_FEEDS_PATH)) or str(DEFAULT_FEEDS_PATH))
    return Settings(
        db_path=db_path if db_path.is_absolute() else ROOT / db_path,
        feeds_path=feeds_path if feeds_path.is_absolute() else ROOT / feeds_path,
        app_password=_setting("APP_PASSWORD"),
        daily_limit=int(_setting("NEWS_DAILY_LIMIT", "12") or "12"),
        exploration_count=int(_setting("NEWS_EXPLORATION_COUNT", "2") or "2"),
    )


def load_feeds(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
