from __future__ import annotations

import hmac
import json

import streamlit as st

from news_curator.config import load_feeds, load_settings
from news_curator.static_store import load_store, record_feedback, select_daily_articles


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


def load_today_articles() -> list[dict]:
    settings = load_settings()
    feeds = load_feeds(settings.feeds_path)
    feed_weights = {feed["name"]: float(feed.get("base_weight", 0.8)) for feed in feeds}
    return select_daily_articles(feed_weights, settings.daily_limit, settings.exploration_count)


def feedback(article_url: str, action: str) -> None:
    record_feedback(article_url, action)


def render_article(article: dict, index: int, total: int) -> None:
    tags = article.get("tags") or []
    bucket = "探索枠" if article.get("selected_bucket") == "exploration" else "推薦"
    st.caption(f"{index + 1}/{total} - {bucket} - {article['source']}")
    st.subheader(article.get("jp_title") or article["title"])
    st.write(article.get("jp_summary") or article.get("summary") or "")
    if tags:
        st.write(" ".join(f"`{tag}`" for tag in tags))
    if article.get("published_at"):
        st.caption(f"published: {article['published_at']}")

    cols = st.columns(4)
    if cols[0].button("役に立った", use_container_width=True):
        feedback(article["url"], "useful")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[1].button("不要", use_container_width=True):
        feedback(article["url"], "bad")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[2].button("あとで読む", use_container_width=True):
        feedback(article["url"], "later")
        st.session_state.card_index = min(index + 1, total)
        st.rerun()
    if cols[3].link_button("元記事", article["url"], use_container_width=True):
        feedback(article["url"], "opened")


def render_intro() -> None:
    st.title("個人ニュースキュレーター")
    st.caption("RSS記事を日本語で要約し、あなたの反応をもとに次回の推薦を調整します。")

    with st.container(border=True):
        st.markdown(
            """
            このアプリは、事前に収集・要約されたRSS記事を表示するためのビューアです。
            Streamlit Cloud上ではOpenAI APIを呼び出さず、`data/news_items.json` に保存された要約済みデータだけを読み込みます。
            RSS取得はバッチ処理、記事要約はCodex Automationで行う想定です。

            使い方:
            1. 今日のカードを1件ずつ確認します。
            2. 各カードで「役に立った」「不要」「あとで読む」「元記事」を選びます。
            3. フィードバックは表示順の調整に使われます。
            4. 新しい記事は、RSSバッチとCodex Automationが更新したあとに表示されます。
            """
        )


def main() -> None:
    if not require_password():
        return

    render_intro()

    with st.sidebar:
        store = load_store()
        st.header("データ")
        st.caption(f"保存記事: {len(store['articles'])}件")
        st.caption(f"最終更新: {store.get('generated_at') or '未更新'}")

        st.header("表示")
        if st.button("先頭のカードに戻る", use_container_width=True):
            st.session_state.card_index = 0
            st.rerun()

        if st.session_state.get("authenticated") and st.button("ロック", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    articles = load_today_articles()
    if not articles:
        st.info("まだ表示できる要約済み記事がありません。RSSバッチとCodex Automationの更新後に表示されます。")
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
                f"- [{row.get('jp_title') or row['title']}]({row['url']}) - {row['source']} - `{row.get('selected_bucket')}`"
            )


if __name__ == "__main__":
    main()
