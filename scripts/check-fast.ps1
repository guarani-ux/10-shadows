# scripts/check-fast.ps1
$ErrorActionPreference = "Stop"
python scripts/check_fast.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
