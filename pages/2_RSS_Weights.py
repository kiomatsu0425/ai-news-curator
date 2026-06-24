from __future__ import annotations

import streamlit as st

from news_curator.postgres_store import source_weight_rows
from news_curator.streamlit_ui import APP_TITLE, load_feed_definitions, require_password


st.set_page_config(page_title=f"{APP_TITLE} - RSS取得先と重み", layout="wide")


@st.cache_data(show_spinner=False, ttl=60)
def load_source_weights() -> list[dict]:
    feeds, _, _ = load_feed_definitions()
    return source_weight_rows(feeds)


def main() -> None:
    if not require_password():
        return

    st.title("RSS取得先と重み")
    st.caption("RSS取得先の設定値と、フィードバックから学習した source weight を確認できます。")

    try:
        rows = load_source_weights()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    if not rows:
        st.info("RSS取得先が設定されていません。")
        return

    table_rows = [
        {
            "source name": row["name"],
            "topic": row["topic"],
            "feed url": row["url"],
            "base_weight": row["base_weight"],
            "learned_weight": row["learned_weight"],
            "effective_weight": row["effective_weight"],
        }
        for row in rows
    ]
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={"feed url": st.column_config.LinkColumn("feed url")},
    )


if __name__ == "__main__":
    main()
