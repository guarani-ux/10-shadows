# scripts/check-full.ps1
$ErrorActionPreference = "Stop"
python scripts/check_full.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
