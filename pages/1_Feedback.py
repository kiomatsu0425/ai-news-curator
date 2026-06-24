from __future__ import annotations

import streamlit as st

from news_curator.postgres_store import latest_feedback_by_article
from news_curator.streamlit_ui import ACTION_LABELS, APP_TITLE, require_password


st.set_page_config(page_title=f"{APP_TITLE} - 過去のフィードバック", layout="wide")


@st.cache_data(show_spinner=False, ttl=30)
def load_feedback_rows() -> list[dict]:
    return latest_feedback_by_article(limit=500)


def main() -> None:
    if not require_password():
        return

    st.title("過去のフィードバック")
    st.caption("記事ごとの最新の反応を確認できます。")

    try:
        rows = load_feedback_rows()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    if not rows:
        st.info("まだフィードバックはありません。")
        return

    table_rows = [
        {
            "最終反応日時": row["created_at"],
            "最終反応": ACTION_LABELS.get(row["action"], row["action"]),
            "記事タイトル": row["display_title"],
            "source": row.get("source") or "",
            "元記事リンク": row["url"],
        }
        for row in rows
    ]
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={"元記事リンク": st.column_config.LinkColumn("元記事リンク")},
    )


if __name__ == "__main__":
    main()
