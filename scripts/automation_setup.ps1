$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "dependency install failed" }

& $python -m compileall app.py news_curator scripts
if ($LASTEXITCODE -ne 0) { throw "compileall failed" }

& $python scripts\list_pending_summaries.py --limit 1 | Out-File -Encoding utf8 $env:TEMP\pending_summaries_preview.json
if ($LASTEXITCODE -ne 0) { throw "pending summary preview failed" }
