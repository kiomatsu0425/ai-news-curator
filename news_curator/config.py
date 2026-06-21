from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path: Path, *args: Any, **kwargs: Any) -> bool:
        if not path.exists():
            return False
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return True


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FEEDS_PATH = ROOT / "feeds.json"


@dataclass(frozen=True)
class Settings:
    database_url: str | None
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
    feeds_path = Path(_setting("NEWS_FEEDS_PATH", str(DEFAULT_FEEDS_PATH)) or str(DEFAULT_FEEDS_PATH))
    return Settings(
        database_url=_setting("DATABASE_URL"),
        feeds_path=feeds_path if feeds_path.is_absolute() else ROOT / feeds_path,
        app_password=_setting("APP_PASSWORD"),
        daily_limit=int(_setting("NEWS_DAILY_LIMIT", "12") or "12"),
        exploration_count=int(_setting("NEWS_EXPLORATION_COUNT", "2") or "2"),
    )


def load_feeds(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
