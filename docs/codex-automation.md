# Codex Automation Flow

This app should not call the OpenAI API from Streamlit Cloud.

Use this split:

1. RSS batch job updates `data/news_items.json` with raw articles.
2. Codex Automation summarizes pending articles by editing `data/news_items.json`.
3. Streamlit Cloud only reads `data/news_items.json` and displays summarized cards.

## RSS Fetch Batch

Run this from the repository:

```powershell
python scripts\fetch_rss_batch.py --max-items-per-feed 12
git add data/news_items.json
git commit -m "Fetch RSS articles"
git push
```

This does not call any LLM or OpenAI API.

## Codex Automation Prompt

Create a daily Codex Automation using this prompt:

```text
In repository kiomatsu0425/ai-news-curator, summarize pending RSS articles without using the OpenAI API.

Steps:
1. Pull the latest main branch.
2. Run: python scripts/reset_mojibake_summaries.py
3. Run: python scripts/list_pending_summaries.py --limit 12
4. Open data/news_items.json as UTF-8.
5. For each pending article, fill:
   - jp_title: natural Japanese title
   - jp_summary: Japanese 3-line summary
   - tags: 2 to 5 concise Japanese or English topic tags
6. Japanese text must be real UTF-8 Japanese. Do not replace Japanese characters with question marks. Do not write mojibake such as "????".
7. Before committing, run: python scripts/list_pending_summaries.py --limit 12
8. If an article still appears pending only because of "????" or broken Japanese, fix it before committing.
9. Do not change existing feedback.
10. Commit and push data/news_items.json with message:
   "Summarize RSS articles"

Keep summaries concise and useful for deciding whether to read the original article.
```

Codex Automation uses Codex to perform the summarization work in the repo. The Streamlit app does not make API calls.

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

The setup script only installs Python dependencies and runs light validation. It does not fetch RSS and does not summarize articles.

The cleanup script removes generated Python caches and prints `git status --short`. It intentionally does not delete `data/news_items.json`, because that file is the shared artifact updated by the RSS batch and Codex Automation.
