$ErrorActionPreference = "Stop"

$targets = @("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
foreach ($target in $targets) {
    Get-ChildItem -Path . -Recurse -Force -Directory -Filter $target -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
}

git status --short

