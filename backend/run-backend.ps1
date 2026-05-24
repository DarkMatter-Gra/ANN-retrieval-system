$ErrorActionPreference = 'Stop'

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendRoot

if (Test-Path '.\.venv\Scripts\Activate.ps1') {
  . '.\.venv\Scripts\Activate.ps1'
}

if (Get-Command uvicorn -ErrorAction SilentlyContinue) {
  uvicorn app.main:app --reload --port 8000
} else {
  python -m uvicorn app.main:app --reload --port 8000
}
