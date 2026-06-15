from __future__ import annotations

import json
import sqlite3
from datetime import date

import streamlit as st

from news_curator.config import load_feeds, load_settings
from news_curator.db import connect, init_db, record_feedback
from news_curator.pipeline import run_daily
from news_curator.ranker import score_articles, select_daily


st.set_page_config(page_title="Personal News Curator", layout="centered")


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
    bucket = "探索" if article["selected_bucket"] == "exploration" else "推薦"
    st.caption(f"{index + 1}/{total} · {bucket} · {article['source']}")
    st.subheader(article["jp_title"] or article["title"])
    st.write(article["jp_summary"] or article["summary"] or "")
    if tags:
        st.write(" ".join(f"`{tag}`" for tag in tags))
    st.caption(f"score {article['score']:.2f}")

    cols = st.columns(4)
    if cols[0].button("役に立った", use_container_width=True):
        feedback(article["id"], "useful")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[1].button("不要", use_container_width=True):
        feedback(article["id"], "bad")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[2].button("あとで読む", use_container_width=True):
        feedback(article["id"], "later")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[3].link_button("元記事", article["url"], use_container_width=True):
        feedback(article["id"], "opened")


def main() -> None:
    st.title("Personal News Curator")
    st.caption("RSSから集めた記事を日本語要約し、あなたのフィードバックで次回の推薦を調整します。")

    with st.sidebar:
        st.header("Daily job")
        if st.button("RSS取得・要約を実行", use_container_width=True):
            with st.spinner("RSSを取得して要約しています..."):
                stats = run_daily()
            st.success(f"取得 {stats['fetched']}件 / 要約 {stats['summarized']}件 / 本日表示 {stats['selected']}件")
            st.session_state.card_index = 0

        st.header("表示")
        if st.button("先頭に戻る", use_container_width=True):
            st.session_state.card_index = 0
            st.rerun()

    articles = load_today_articles()
    if not articles:
        st.info("まだ記事がありません。サイドバーの「RSS取得・要約を実行」を押してください。")
        return

    st.session_state.setdefault("card_index", 0)
    index = min(st.session_state.card_index, len(articles))
    if index >= len(articles):
        st.success("今日のカードは見終わりました。")
        st.session_state.card_index = 0
        return

    render_article(articles[index], index, len(articles))

    with st.expander("今日の12件"):
        for row in articles:
            st.markdown(f"- [{row['jp_title'] or row['title']}]({row['url']}) · {row['source']} · `{row['selected_bucket']}`")


if __name__ == "__main__":
    main()
