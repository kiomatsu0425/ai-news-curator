#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt

"$PYTHON_BIN" -m compileall app.py news_curator scripts
"$PYTHON_BIN" scripts/list_pending_summaries.py --limit 1 >/tmp/pending_summaries_preview.json
