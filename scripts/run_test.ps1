# Convenience script: run the full test suite.
# Usage:  .\scripts\run_test.ps1
Set-Location (Join-Path $PSScriptRoot '..')
python -m pytest -q
exit $LASTEXITCODE