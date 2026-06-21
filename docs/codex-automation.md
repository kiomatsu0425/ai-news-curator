# Codex Automation Flow

This app should not call the OpenAI API from Streamlit Cloud.

Use this split:

1. RSS batch job saves raw articles to Neon Postgres.
2. Codex Automation summarizes pending articles and saves summaries to Neon Postgres.
3. Streamlit Cloud reads summarized articles from Neon Postgres and records feedback there.

## Required Secrets

For local Codex Automation execution, keep the Neon connection string in the repository root `.env` file:

```text
DATABASE_URL=postgresql://user:password@host.neon.tech/dbname?sslmode=require
```

Set it once before running the automation. If it is missing or invalid, stop and ask the user to set it. Do not try to retrieve credentials during an automation run.

The value comes from Neon Console > Project > Connect. Use the pooled connection string when available, preferably with a hostname that contains `-pooler`.

Also set the same value once in GitHub Actions Secrets and Streamlit Cloud Secrets.

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
- The app stores articles, summaries, feedback, and ranking weights in Neon Postgres.
- For local Codex Automation execution, read DATABASE_URL from the repository root `.env` file.
- The `.env` file is the only local source of the Neon connection string during automation runs.
- If DATABASE_URL is missing or the database connection fails because of credentials, stop and report that the user must update `.env`.
- Do not open Neon Console or try to retrieve credentials during the automation run.
- Do not edit data/news_items.json. It is legacy import data only.
- Do not commit generated article data back to GitHub.

Steps:
1. Pull the latest main branch.
2. Ensure dependencies are installed if needed: python -m pip install -r requirements.txt
3. Run: python scripts/reset_mojibake_summaries.py
4. Run: python scripts/list_pending_summaries.py --limit 12
5. For each pending article returned from Neon Postgres, create:
   - jp_title: natural Japanese title
   - jp_summary: Japanese 3-line summary
   - tags: 2 to 5 concise Japanese or English topic tags
6. Japanese text must be real UTF-8 Japanese. Do not replace Japanese characters with question marks. Do not write mojibake such as "????".
7. Save each summarized article to Neon Postgres with:
   python scripts/save_summary.py --url "<article URL>" --jp-title "<Japanese title>" --jp-summary "<Japanese summary>" --tags-json '["tag1","tag2"]'
8. Run: python scripts/list_pending_summaries.py --limit 12
9. If an article still appears pending only because of "????" or broken Japanese, fix it with scripts/save_summary.py before finishing.

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
