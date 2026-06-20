# Personal News Curator

RSS記事を収集し、Codex Automationで要約し、Streamlit Cloudで表示する個人用ニュースキュレーターです。

Streamlit Cloud上ではOpenAI APIを呼び出しません。API課金を避けるため、処理を次の3つに分けています。

1. RSS取得: バッチプログラムが `data/news_items.json` に記事本文を保存
2. LLM要約: Codex Automationが未要約記事を読み、要約をJSONに追記
3. 表示: Streamlit Cloudが `data/news_items.json` を読むだけ

## ローカルセットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

ローカルで起動:

```powershell
streamlit run app.py
```

## Streamlit Cloud Secrets

```toml
APP_PASSWORD = "好きなパスワード"
NEWS_DAILY_LIMIT = "12"
NEWS_EXPLORATION_COUNT = "2"
```

`APP_PASSWORD` を設定すると、表示前にパスワード入力画面が出ます。

## RSS取得バッチ

RSSを取得して `data/news_items.json` に保存します。LLMやOpenAI APIは呼びません。

```powershell
python scripts\fetch_rss_batch.py --max-items-per-feed 12
git add data/news_items.json
git commit -m "Fetch RSS articles"
git push
```

GitHub Actionsにも `.github/workflows/fetch-rss.yml` を用意しています。毎日 07:00 JST にRSSを取得し、変更があれば `data/news_items.json` をコミットします。GitHubのActions画面から手動実行もできます。

## Codex Automationによる要約

Codex Automationには [docs/codex-automation.md](docs/codex-automation.md) のプロンプトを登録します。

Automationは次を行います。

- `scripts/list_pending_summaries.py` で未要約記事を確認
- `data/news_items.json` の `jp_title`, `jp_summary`, `tags` を埋める
- コミットしてGitHubへpush

Automationのローカル環境には次を設定します。

Setup:

```bash
bash scripts/automation_setup.sh
```

Cleanup:

```bash
bash scripts/automation_cleanup.sh
```

## RSSの追加

RSS一覧は `feeds.json` です。

```json
{
  "name": "Example Feed",
  "url": "https://example.com/feed.xml",
  "topic": "ai",
  "base_weight": 0.9
}
```

`base_weight` は表示順位の初期重みです。だいたい `0.8` から `1.1` の範囲で調整します。
