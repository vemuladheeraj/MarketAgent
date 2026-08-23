# Convenience script: start the Phase-1 application.
# (defaults to config/default.yaml; set APP_CONFIG_PATH to override).
# Usage:  .\scripts\run_app.ps1
Set-Location (Join-Path $PSScriptRoot '..')
python -m app.main
exit $LASTEXITCODE