$ErrorActionPreference = 'Stop'

$frontendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $frontendRoot

if (-not (Test-Path '.\node_modules')) {
  Write-Host 'node_modules not found. Running npm install...' -ForegroundColor Yellow
  npm install
}

npm run dev
