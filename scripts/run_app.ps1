# Convenience script: run the MarketAgent once (single analysis cycle).
# (defaults to config/default.yaml; set APP_CONFIG_PATH to override).
# Usage:  .\scripts\run_app.ps1
Set-Location (Join-Path $PSScriptRoot '..')
python -m app.main
exit $LASTEXITCODE