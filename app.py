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


st.set_page_config(page_title="個人ニュースキュレーター", layout="centered")


def require_password() -> bool:
    settings = load_settings()
    if not settings.app_password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("個人ニュースキュレーター")
    st.caption("続行するにはアプリのパスワードを入力してください。")

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
    bucket = "探索枠" if article["selected_bucket"] == "exploration" else "推薦"
    st.caption(f"{index + 1}/{total} - {bucket} - {article['source']}")
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


def render_intro() -> None:
    st.title("個人ニュースキュレーター")
    st.caption("RSS記事を日本語で要約し、あなたの反応をもとに次回の推薦を調整します。")

    with st.container(border=True):
        st.markdown(
            """
            このアプリは、登録したRSSフィードから記事を集め、OpenAI APIで日本語タイトル・3行要約・タグを作ります。
            表示された記事に「役に立った」「不要」「あとで読む」を付けると、タグや配信元の好みが保存され、次回以降の並び順に反映されます。

            使い方:
            1. 左のサイドバーで「RSS取得・要約を実行」を押します。
            2. 今日のカードを1件ずつ確認します。
            3. 各カードで「役に立った」「不要」「あとで読む」「元記事」を選びます。
            4. 次回取得時は、好み・新しさ・探索枠を組み合わせて12件を表示します。
            """
        )


def main() -> None:
    if not require_password():
        return

    render_intro()

    with st.sidebar:
        st.header("日次処理")
        if st.button("RSS取得・要約を実行", use_container_width=True):
            with st.spinner("RSSを取得し、記事を要約しています..."):
                stats = run_daily()
            st.success(
                f"取得 {stats['fetched']}件 / 要約 {stats['summarized']}件 / 表示 {stats['selected']}件"
            )
            if stats.get("rate_limited"):
                st.warning(
                    "OpenAI APIのレート制限またはクォータに達しました。取得済み記事は保存し、API要約だけ停止しました。"
                    "時間を置いて再実行するか、NEWS_MAX_SUMMARIES_PER_RUNを小さくしてください。"
                )
            st.session_state.card_index = 0

        st.header("表示")
        if st.button("先頭のカードに戻る", use_container_width=True):
            st.session_state.card_index = 0
            st.rerun()

        if st.session_state.get("authenticated") and st.button("ロック", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    articles = load_today_articles()
    if not articles:
        st.info("まだ記事がありません。左のサイドバーから「RSS取得・要約を実行」を押してください。")
        return

    st.session_state.setdefault("card_index", 0)
    index = min(st.session_state.card_index, len(articles))
    if index >= len(articles):
        st.success("今日のカードはすべて確認しました。")
        st.session_state.card_index = 0
        return

    render_article(articles[index], index, len(articles))

    with st.expander("今日の選定記事"):
        for row in articles:
            st.markdown(
                f"- [{row['jp_title'] or row['title']}]({row['url']}) - {row['source']} - `{row['selected_bucket']}`"
            )


if __name__ == "__main__":
    main()
