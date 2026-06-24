from __future__ import annotations

import hmac
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from .config import load_feeds, load_settings


APP_TITLE = "個人ニュースキュレーター"
ACTION_LABELS = {
    "useful": "役に立った",
    "bad": "不要",
    "later": "あとで読む",
    "opened": "元記事を開いた",
}
JST = ZoneInfo("Asia/Tokyo")


def format_jst(value: object, default: str = "未更新") -> str:
    if value in (None, ""):
        return default

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def require_password() -> bool:
    settings = load_settings()
    if not settings.app_password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title(APP_TITLE)
    st.caption("続けるにはアプリのパスワードを入力してください。")

    with st.form("password_form"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("開く", use_container_width=True)

    if submitted:
        if hmac.compare_digest(password, settings.app_password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います。")

    return False


def load_feed_definitions() -> tuple[list[dict], int, int]:
    settings = load_settings()
    feeds = load_feeds(settings.feeds_path)
    return feeds, settings.daily_limit, settings.exploration_count
