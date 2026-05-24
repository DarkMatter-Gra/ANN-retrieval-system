$ErrorActionPreference = 'Stop'

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendRoot

if (Test-Path '.\.venv\Scripts\Activate.ps1') {
  . '.\.venv\Scripts\Activate.ps1'
}

if (Get-Command celery -ErrorAction SilentlyContinue) {
  celery -A app.tasks.celery_app.celery_app worker --pool=solo --loglevel=INFO
} else {
  python -m celery -A app.tasks.celery_app.celery_app worker --pool=solo --loglevel=INFO
}
