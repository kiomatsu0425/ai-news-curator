# Codex Automation Flow

This app should not call the OpenAI API from Streamlit Cloud.

Use this split:

1. RSS batch job saves raw articles to Neon Postgres.
2. Codex Automation summarizes pending articles and saves summaries to Neon Postgres.
3. Streamlit Cloud reads summarized articles from Neon Postgres and records feedback there.

## Required Secrets

Set this value in the Automation environment, GitHub Actions Secrets, and Streamlit Cloud Secrets:

```text
DATABASE_URL=postgresql://user:password@host.neon.tech/dbname?sslmode=require
```

## RSS Fetch Batch

Run this from the repository:

```powershell
python scripts\fetch_rss_batch.py --max-items-per-feed 12
```

This does not call any LLM or OpenAI API.

## Codex Automation Prompt

Create a daily Codex Automation using this prompt:

```text
In repository kiomatsu0425/ai-news-curator, summarize pending RSS articles without using the OpenAI API.

Environment:
- DATABASE_URL is configured with the Neon Postgres connection string.
- Do not edit data/news_items.json. It is legacy import data only.
- Do not commit generated article data back to GitHub.

Steps:
1. Pull the latest main branch.
2. Run: python scripts/reset_mojibake_summaries.py
3. Run: python scripts/list_pending_summaries.py --limit 12
4. For each pending article, create:
   - jp_title: natural Japanese title
   - jp_summary: Japanese 3-line summary
   - tags: 2 to 5 concise Japanese or English topic tags
5. Japanese text must be real UTF-8 Japanese. Do not replace Japanese characters with question marks. Do not write mojibake such as "????".
6. Save each summarized article with:
   python scripts/save_summary.py --url "<article URL>" --jp-title "<Japanese title>" --jp-summary "<Japanese summary>" --tags-json '["tag1","tag2"]'
7. Run: python scripts/list_pending_summaries.py --limit 12
8. If an article still appears pending only because of "????" or broken Japanese, fix it with scripts/save_summary.py before finishing.

Keep summaries concise and useful for deciding whether to read the original article.
```

## Local Environment Scripts

Use these scripts for the Automation local environment.

Setup script:

```bash
bash scripts/automation_setup.sh
```

Cleanup script:

```bash
bash scripts/automation_cleanup.sh
```

If the environment is Windows/PowerShell, use these instead:

```powershell
.\scripts\automation_setup.ps1
.\scripts\automation_cleanup.ps1
```

The setup script installs Python dependencies and runs light validation. It does not fetch RSS and does not summarize articles.

The cleanup script removes generated Python caches and prints `git status --short`. It intentionally does not delete `data/news_items.json`, because that file is legacy import data.
