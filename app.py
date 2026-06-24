from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date
from typing import Any

import streamlit as st

from news_curator.postgres_store import record_feedback, select_daily_articles, store_stats
from news_curator.streamlit_ui import ACTION_LABELS, APP_TITLE, load_feed_definitions, require_password


FEEDBACK_EXECUTOR = ThreadPoolExecutor(max_workers=2)


st.set_page_config(page_title=APP_TITLE, layout="centered")


def build_feed_weights() -> tuple[str, dict[str, float], int, int]:
    feeds, daily_limit, exploration_count = load_feed_definitions()
    feeds_json = json.dumps(feeds, ensure_ascii=False, sort_keys=True)
    feed_weights = {feed["name"]: float(feed.get("base_weight", 0.8)) for feed in feeds}
    return feeds_json, feed_weights, daily_limit, exploration_count


@st.cache_data(show_spinner=False, ttl=60)
def load_dashboard_snapshot(
    today_key: str,
    feeds_json: str,
    daily_limit: int,
    exploration_count: int,
) -> dict[str, Any]:
    feeds = json.loads(feeds_json)
    feed_weights = {feed["name"]: float(feed.get("base_weight", 0.8)) for feed in feeds}
    return {
        "articles": select_daily_articles(feed_weights, daily_limit, exploration_count),
        "stats": store_stats(),
        "day": today_key,
    }


def _record_feedback_job(article_url: str, action: str) -> None:
    record_feedback(article_url, action)


def ensure_state_defaults() -> None:
    st.session_state.setdefault("articles", [])
    st.session_state.setdefault("stats", {"articles": 0, "feedback": 0, "generated_at": None})
    st.session_state.setdefault("dashboard_day", "")
    st.session_state.setdefault("card_index", 0)
    st.session_state.setdefault("pending_feedbacks", [])
    st.session_state.setdefault("pending_feedback_keys", set())
    st.session_state.setdefault("completed_feedback_keys", set())
    st.session_state.setdefault("feedback_future", None)
    st.session_state.setdefault("feedback_future_key", None)
    st.session_state.setdefault("feedback_error", None)


def hydrate_dashboard(force: bool = False) -> None:
    ensure_state_defaults()
    today_key = date.today().isoformat()
    feeds_json, _, daily_limit, exploration_count = build_feed_weights()
    needs_refresh = force or st.session_state.dashboard_day != today_key or not st.session_state.articles
    if not needs_refresh:
        return

    snapshot = load_dashboard_snapshot(today_key, feeds_json, daily_limit, exploration_count)
    st.session_state.articles = snapshot["articles"]
    st.session_state.stats = snapshot["stats"]
    if st.session_state.dashboard_day != today_key:
        st.session_state.card_index = 0
        st.session_state.pending_feedbacks = []
        st.session_state.completed_feedback_keys = set()
        st.session_state.pending_feedback_keys = set()
        st.session_state.feedback_future = None
        st.session_state.feedback_future_key = None
        st.session_state.feedback_error = None
    st.session_state.dashboard_day = today_key
    st.session_state.card_index = min(st.session_state.card_index, len(st.session_state.articles))


def process_feedback_queue() -> None:
    future: Future | None = st.session_state.feedback_future
    if future is not None and future.done():
        exc = future.exception()
        key = st.session_state.feedback_future_key
        if exc is not None:
            st.session_state.feedback_error = f"フィードバック保存に失敗しました: {exc}"
            if key is not None:
                st.session_state.pending_feedback_keys.discard(key)
        else:
            st.session_state.feedback_error = None
            if key is not None:
                st.session_state.pending_feedback_keys.discard(key)
                st.session_state.completed_feedback_keys.add(key)
            load_dashboard_snapshot.clear()
        st.session_state.feedback_future = None
        st.session_state.feedback_future_key = None

    if st.session_state.feedback_future is not None or not st.session_state.pending_feedbacks:
        return

    item = st.session_state.pending_feedbacks.pop(0)
    st.session_state.feedback_future = FEEDBACK_EXECUTOR.submit(
        _record_feedback_job,
        item["url"],
        item["action"],
    )
    st.session_state.feedback_future_key = item["key"]


def queue_feedback(article_url: str, action: str, advance_card: bool) -> None:
    key = f"{article_url}:{action}"
    if key in st.session_state.pending_feedback_keys:
        return
    if key == st.session_state.feedback_future_key:
        return
    if key in st.session_state.completed_feedback_keys:
        return

    st.session_state.pending_feedbacks.append({"url": article_url, "action": action, "key": key})
    st.session_state.pending_feedback_keys.add(key)
    st.session_state.feedback_error = None

    stats = dict(st.session_state.stats)
    stats["feedback"] = int(stats.get("feedback", 0)) + 1
    st.session_state.stats = stats

    if advance_card:
        next_index = min(st.session_state.card_index + 1, len(st.session_state.articles))
        st.session_state.card_index = next_index


def reset_to_first_card() -> None:
    st.session_state.card_index = 0


def show_previous_card() -> None:
    st.session_state.card_index = max(0, st.session_state.card_index - 1)


def show_next_card() -> None:
    total = len(st.session_state.articles)
    if total:
        st.session_state.card_index = min(total - 1, st.session_state.card_index + 1)


def render_article(article: dict[str, Any], index: int, total: int) -> None:
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
    cols[0].button(
        ACTION_LABELS["useful"],
        key=f"useful:{article['url']}",
        use_container_width=True,
        on_click=queue_feedback,
        args=(article["url"], "useful", True),
    )
    cols[1].button(
        ACTION_LABELS["bad"],
        key=f"bad:{article['url']}",
        use_container_width=True,
        on_click=queue_feedback,
        args=(article["url"], "bad", True),
    )
    cols[2].button(
        ACTION_LABELS["later"],
        key=f"later:{article['url']}",
        use_container_width=True,
        on_click=queue_feedback,
        args=(article["url"], "later", True),
    )
    if cols[3].link_button("元記事", article["url"], use_container_width=True):
        queue_feedback(article["url"], "opened", False)

    nav_cols = st.columns(2)
    nav_cols[0].button(
        "戻る",
        use_container_width=True,
        disabled=index <= 0,
        on_click=show_previous_card,
    )
    nav_cols[1].button(
        "進む",
        use_container_width=True,
        disabled=index >= total - 1,
        on_click=show_next_card,
    )


def render_intro() -> None:
    st.title(APP_TITLE)
    st.caption("RSS記事を日本語で要約し、あなたの反応をもとに次回の推薦を調整します。")

    with st.container(border=True):
        st.markdown(
            """
            このアプリは、事前に収集・要約されたRSS記事を表示するためのビューアです。
            Streamlit Cloud上ではOpenAI APIを呼び出さず、Neon Postgresに保存された要約済みデータだけを読み込みます。
            RSS取得はバッチ処理、記事要約はCodex Automationで行う想定です。

            使い方:
            1. 今日のカードを1件ずつ確認します。
            2. 各カードで「役に立った」「不要」「あとで読む」「元記事」を選びます。
            3. フィードバックは表示順の調整に使われます。
            4. 新しい記事は、RSSバッチとCodex Automationが更新したあとに表示されます。
            """
        )


def render_sidebar() -> None:
    stats = st.session_state.stats
    with st.sidebar:
        st.header("データ")
        st.caption(f"保存記事: {stats['articles']}件")
        st.caption(f"フィードバック: {stats['feedback']}件")
        st.caption(f"最終更新: {stats.get('generated_at') or '未更新'}")

        if st.session_state.feedback_future is not None or st.session_state.pending_feedbacks:
            st.caption("フィードバックを同期中...")
        if st.session_state.feedback_error:
            st.warning(st.session_state.feedback_error)

        st.header("表示")
        st.button(
            "先頭のカードに戻る",
            use_container_width=True,
            on_click=reset_to_first_card,
        )

        if st.session_state.get("authenticated") and st.button("ロック", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()


def main() -> None:
    if not require_password():
        return

    hydrate_dashboard()
    process_feedback_queue()
    render_intro()
    render_sidebar()

    articles = st.session_state.articles
    if not articles:
        st.info(
            "まだ表示できる要約済み記事がありません。RSSバッチとCodex Automationの更新後に表示されます。"
        )
        return

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
