# Personal News Curator

RSS feeds are collected, summarized in Japanese with the OpenAI API, stored in SQLite, and shown as daily Streamlit cards. Feedback from each card adjusts future ranking by tag and source preference.

## Features

- Fetch articles from RSS feeds listed in `feeds.json`
- Generate Japanese title, 3-line summary, and tags with the OpenAI API
- Store articles, feedback, source weights, and tag weights in SQLite
- Show one article card at a time in Streamlit
- Record "useful", "not needed", "read later", and "opened" feedback
- Rank by freshness, tag preference, source preference, and source base weight
- Select 12 articles per day, including 2 exploration items

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set your OpenAI API key in `.env`.

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
NEWS_DB_PATH=data/news_curator.sqlite3
NEWS_DAILY_LIMIT=12
NEWS_EXPLORATION_COUNT=2
```

Run the app:

```powershell
streamlit run app.py
```

Open the displayed local URL, usually `http://localhost:8501`.

## Streamlit Community Cloud

This repository can be deployed directly to Streamlit Community Cloud.

1. Go to `https://share.streamlit.io/`.
2. Create a new app from GitHub.
3. Select repository: `kiomatsu0425/ai-news-curator`.
4. Select branch: `main`.
5. Select entrypoint file: `app.py`.
6. Open "Advanced settings" and add secrets.

Use these secrets:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1-mini"
NEWS_DB_PATH = "data/news_curator.sqlite3"
NEWS_DAILY_LIMIT = "12"
NEWS_EXPLORATION_COUNT = "2"
```

The app reads settings from environment variables first, then from `st.secrets`. This means the same code works locally and on Streamlit Community Cloud.

## Important Note About SQLite On Cloud

SQLite works for the first cloud deployment and is enough to confirm smartphone access. However, Streamlit Community Cloud storage should be treated as app-local and not as a durable production database. For long-term use, move the database to Supabase Postgres or another managed database.

## Daily Fetch

From the Streamlit UI, click "RSS取得・要約を実行" in the sidebar.

For local scheduled execution:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\fetch_daily.py
```

For cloud scheduled execution, the next recommended step is GitHub Actions plus a cloud database.

## Add Feeds

Edit `feeds.json`:

```json
{
  "name": "Example Feed",
  "url": "https://example.com/feed.xml",
  "topic": "ai",
  "base_weight": 0.9
}
```

`base_weight` is the source's initial preference weight. Feedback adjusts `source_weights` and `tag_weights` automatically.

