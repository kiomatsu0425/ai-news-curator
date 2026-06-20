from __future__ import annotations

import hmac
import json
import sqlite3
from datetime import date

import streamlit as st

from news_curator.config import load_feeds, load_settings
from news_curator.db import connect, init_db, record_feedback
from news_curator.pipeline import run_daily
from news_curator.ranker import score_articles, select_daily


st.set_page_config(page_title="Personal News Curator", layout="centered")


def require_password() -> bool:
    settings = load_settings()
    if not settings.app_password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("Personal News Curator")
    st.caption("Enter the app password to continue.")

    with st.form("password_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Unlock", use_container_width=True)

    if submitted:
        if hmac.compare_digest(password, settings.app_password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


def load_today_articles() -> list[sqlite3.Row]:
    settings = load_settings()
    feeds = load_feeds(settings.feeds_path)
    feed_weights = {feed["name"]: float(feed.get("base_weight", 0.8)) for feed in feeds}
    with connect(settings.db_path) as conn:
        init_db(conn)
        score_articles(conn, feed_weights)
        return select_daily(conn, settings.daily_limit, settings.exploration_count, today=date.today())


def feedback(article_id: int, action: str) -> None:
    settings = load_settings()
    with connect(settings.db_path) as conn:
        init_db(conn)
        record_feedback(conn, article_id, action)


def render_article(article: sqlite3.Row, index: int, total: int) -> None:
    tags = json.loads(article["tags_json"] or "[]")
    bucket = "Explore" if article["selected_bucket"] == "exploration" else "Ranked"
    st.caption(f"{index + 1}/{total} - {bucket} - {article['source']}")
    st.subheader(article["jp_title"] or article["title"])
    st.write(article["jp_summary"] or article["summary"] or "")
    if tags:
        st.write(" ".join(f"`{tag}`" for tag in tags))
    st.caption(f"score {article['score']:.2f}")

    cols = st.columns(4)
    if cols[0].button("Useful", use_container_width=True):
        feedback(article["id"], "useful")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[1].button("Not needed", use_container_width=True):
        feedback(article["id"], "bad")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[2].button("Read later", use_container_width=True):
        feedback(article["id"], "later")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[3].link_button("Open", article["url"], use_container_width=True):
        feedback(article["id"], "opened")


def main() -> None:
    if not require_password():
        return

    st.title("Personal News Curator")
    st.caption("RSS articles are summarized in Japanese and ranked with your feedback.")

    with st.sidebar:
        st.header("Daily job")
        if st.button("Fetch and summarize RSS", use_container_width=True):
            with st.spinner("Fetching RSS feeds and summarizing articles..."):
                stats = run_daily()
            st.success(
                f"Fetched {stats['fetched']} / summarized {stats['summarized']} / selected {stats['selected']}"
            )
            if stats.get("rate_limited"):
                st.warning(
                    "OpenAI rate limit or quota was reached. Saved fetched articles and stopped API summarization. "
                    "Try again later or lower NEWS_MAX_SUMMARIES_PER_RUN."
                )
            st.session_state.card_index = 0

        st.header("View")
        if st.button("Back to first card", use_container_width=True):
            st.session_state.card_index = 0
            st.rerun()

        if st.session_state.get("authenticated") and st.button("Lock", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    articles = load_today_articles()
    if not articles:
        st.info("No articles yet. Click 'Fetch and summarize RSS' in the sidebar.")
        return

    st.session_state.setdefault("card_index", 0)
    index = min(st.session_state.card_index, len(articles))
    if index >= len(articles):
        st.success("You have finished today's cards.")
        st.session_state.card_index = 0
        return

    render_article(articles[index], index, len(articles))

    with st.expander("Today's selected articles"):
        for row in articles:
            st.markdown(
                f"- [{row['jp_title'] or row['title']}]({row['url']}) - {row['source']} - `{row['selected_bucket']}`"
            )


if __name__ == "__main__":
    main()
