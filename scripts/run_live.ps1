# Convenience script: run the MarketAgent live against real market data and
# persist to Firestore continuously so the Web Dashboard shows real-time data.
#
#   - Uses the provider configured in .env (DATA_PROVIDER=indstocks for realtime INDstocks API).
#   - Requires INDSTOCKS_ACCESS_TOKEN in .env (free API — generate at indstocks.com/app/api-trading/access-tokens).
#   - Runs the always-on scheduler loop; cycles only while the NSE session is open (default: every 5s).
#   - Keep this process running in a terminal while you view the dashboard.
#
# Usage:  .\scripts\run_live.ps1
Set-Location (Join-Path $PSScriptRoot '..')
python -m app.main --daemon
exit $LASTEXITCODE