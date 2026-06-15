# Personal News Curator

RSSから記事を集め、OpenAI APIで日本語タイトル・3行要約・タグを作り、Streamlitで1枚ずつ評価する個人用ニュースキュレーターです。

## 機能

- RSSフィード一覧から記事を取得
- OpenAI APIで日本語タイトル、3行要約、タグを生成
- SQLiteに記事・フィードバック・タグ嗜好・ソース嗜好を保存
- Streamlitでカード表示
- 「役に立った」「不要」「あとで読む」「元記事」を記録
- タグ嗜好、ソース嗜好、新しさ、ソース基礎重みでランキング
- 1日12件表示、うち2件は探索枠
- 1ソースに偏りすぎないように上限を設定

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` に `OPENAI_API_KEY` を入れます。モデルは `OPENAI_MODEL` で変更できます。

## 実行

```powershell
streamlit run app.py
```

ブラウザで表示されたURLを開き、サイドバーの「RSS取得・要約を実行」を押すと、RSS取得、要約、ランキング、今日の12件選定まで行います。

## 毎朝の自動実行

Windowsタスクスケジューラでは、仮想環境を有効化したうえで次を実行するタスクを作成します。

```powershell
python scripts/fetch_daily.py
```

Codex Automation、cron、GitHub Actionsに移す場合も、このコマンドを日次実行すれば同じ処理になります。

## RSSの追加

`feeds.json` に次の形式で追加します。

```json
{
  "name": "Example Feed",
  "url": "https://example.com/feed.xml",
  "topic": "ai",
  "base_weight": 0.9
}
```

`base_weight` はそのソースの初期信頼度です。フィードバックが貯まると `source_weights` と `tag_weights` が自動で調整されます。

## データ

既定では `data/news_curator.sqlite3` に保存します。場所を変える場合は `.env` の `NEWS_DB_PATH` を変更してください。

## 次に足すと良いもの

- 類似記事クラスタリング
- embeddingベースの好み学習
- スワイプ操作
- 日本語RSSや日経クロステック系の追加
- ソース別の表示上限をフィードごとに設定

