from __future__ import annotations

import hmac

import streamlit as st

from .config import load_feeds, load_settings


APP_TITLE = "個人ニュースキュレーター"
ACTION_LABELS = {
    "useful": "役に立った",
    "bad": "不要",
    "later": "あとで読む",
    "opened": "元記事を開いた",
}


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
