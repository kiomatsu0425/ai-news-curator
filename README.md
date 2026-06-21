# Personal News Curator

RSS記事を収集し、Codex Automationで日本語要約を作り、Streamlit Cloudでカード形式に表示する個人用ニュースキュレーターです。

Streamlit Cloud上ではOpenAI APIを呼び出しません。記事、要約、フィードバック、推薦用の重みはNeon Postgresに保存します。

## Architecture

1. RSS取得: GitHub ActionsまたはローカルスクリプトがRSSを取得し、Neon Postgresへ保存
2. 要約: Codex Automationが未要約記事を取得し、日本語タイトル・要約・タグをDBへ保存
3. 表示: StreamlitがNeon Postgresから要約済み記事を読み込み、フィードバックを即時保存

GitHubはコード管理とActions実行に使います。`data/news_items.json` は初回移行用の旧データで、通常運用では正データソースにしません。

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

`.env` にはNeonの接続文字列を設定します。

```env
DATABASE_URL=postgresql://user:password@host.neon.tech/dbname?sslmode=require
APP_PASSWORD=change-me
NEWS_DAILY_LIMIT=12
NEWS_EXPLORATION_COUNT=2
```

起動:

```powershell
streamlit run app.py
```

## Streamlit Cloud Secrets

```toml
DATABASE_URL = "postgresql://user:password@host.neon.tech/dbname?sslmode=require"
APP_PASSWORD = "好きなパスワード"
NEWS_DAILY_LIMIT = "12"
NEWS_EXPLORATION_COUNT = "2"
```

`APP_PASSWORD` を設定すると、表示前にパスワード入力画面が出ます。

## Initial Import

旧データの `data/news_items.json` をNeonへ初回投入する場合:

```powershell
python scripts\import_json_to_postgres.py --path data\news_items.json
```

記事、既存要約、タグ、フィードバックをDBへ移します。

## RSS Fetch Batch

RSSを取得してNeon Postgresに保存します。LLMやOpenAI APIは呼びません。

```powershell
python scripts\fetch_rss_batch.py --max-items-per-feed 12
```

GitHub Actionsの `.github/workflows/fetch-rss.yml` も同じ処理を実行します。Repository Secretsに `DATABASE_URL` を設定してください。

## Codex Automation

Codex Automationには [docs/codex-automation.md](docs/codex-automation.md) のプロンプトを登録します。

主な流れ:

- `scripts/list_pending_summaries.py` で未要約記事を確認
- `scripts/save_summary.py` で `jp_title`, `jp_summary`, `tags` をDBへ保存
- `scripts/reset_mojibake_summaries.py` で壊れた日本語要約をリセット

## Feedback

アプリではカードごとに以下を保存します。

- `opened`: +1.0
- `useful`: +0.65
- `bad`: -1.1
- `later`: +0.15

ソース・タグの累積重みを次回の記事選定に使います。`useful` または `bad` 済みの記事は次回以降の候補から除外します。

## RSS Feed Settings

RSS一覧は `feeds.json` です。

```json
{
  "name": "Example Feed",
  "url": "https://example.com/feed.xml",
  "topic": "ai",
  "base_weight": 0.9
}
```

`base_weight` は表示順位の初期重みです。まずは `0.8` から `1.1` の範囲で調整します。
