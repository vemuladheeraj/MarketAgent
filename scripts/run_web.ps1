# Convenience script to launch the MarketAgent Web Dashboard
Set-Location (Join-Path $PSScriptRoot '..\web')
npm.cmd run dev
