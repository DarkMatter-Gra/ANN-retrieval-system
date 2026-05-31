param(
  [switch]$NoBrowser,
  [switch]$ReinstallBackend,
  [switch]$ReinstallFrontend
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$bootstrapRoot = Join-Path $projectRoot '.bootstrap'
$backendStamp = Join-Path $bootstrapRoot 'backend-deps.stamp'
$frontendStamp = Join-Path $bootstrapRoot 'frontend-deps.stamp'
$backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
$backendRunner = Join-Path $backendRoot 'run-backend.ps1'
$workerRunner = Join-Path $backendRoot 'run-worker.ps1'
$frontendRunner = Join-Path $frontendRoot 'run-frontend.ps1'
$dataRoot = Join-Path $projectRoot 'data'
$brokerRoot = Join-Path $dataRoot 'celery-broker'

function Write-Step {
  param([string]$Message)
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-ExecutablePath {
  param([string]$CommandName)

  if (Test-Path $CommandName) {
    return $CommandName
  }

  $command = Get-Command $CommandName -ErrorAction SilentlyContinue
  if ($command -and $command.Source) {
    return $command.Source
  }

  return $CommandName
}

function Invoke-External {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [string[]]$Arguments = @(),

    [string]$WorkingDirectory = $projectRoot,

    [string]$Description = $FilePath
  )

  Write-Step $Description
  $resolvedPath = Resolve-ExecutablePath -CommandName $FilePath
  $processPath = $resolvedPath
  $processArguments = $Arguments

  if ([System.IO.Path]::GetExtension($resolvedPath).Equals('.ps1', [System.StringComparison]::OrdinalIgnoreCase)) {
    $processPath = 'powershell.exe'
    $processArguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$resolvedPath`"") + $Arguments
  }

  $process = Start-Process -FilePath $processPath -ArgumentList $processArguments -WorkingDirectory $WorkingDirectory -NoNewWindow -Wait -PassThru
  if ($process.ExitCode -ne 0) {
    throw "Command failed: $processPath $($processArguments -join ' ')"
  }
}

function Test-PyVersion {
  param([string]$Version)

  try {
    & py "-$Version" --version *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Resolve-PythonLauncher {
  foreach ($version in @('3.11', '3.12', '3.13')) {
    if (Test-PyVersion -Version $version) {
      return @{
        FilePath = 'py'
        Arguments = @("-$version")
        Version = $version
      }
    }
  }

  return $null
}

function Ensure-Python {
  foreach ($preferredVersion in @('3.11', '3.12')) {
    if (Test-PyVersion -Version $preferredVersion) {
      return @{
        FilePath = 'py'
        Arguments = @("-$preferredVersion")
        Version = $preferredVersion
      }
    }
  }

  if (Get-Command winget -ErrorAction SilentlyContinue) {
    try {
      Invoke-External -FilePath 'winget' -Arguments @(
        'install',
        '-e',
        '--id', 'Python.Python.3.11',
        '--accept-package-agreements',
        '--accept-source-agreements',
        '--silent'
      ) -Description 'Install Python 3.11 automatically'
    } catch {
      Write-Host 'Python 3.11 auto-install failed. Falling back to the current version.' -ForegroundColor Yellow
    }

    if (Test-PyVersion -Version '3.11') {
      return @{
        FilePath = 'py'
        Arguments = @('-3.11')
        Version = '3.11'
      }
    }
  }

  if (Test-PyVersion -Version '3.13') {
    return @{
      FilePath = 'py'
      Arguments = @('-3.13')
      Version = '3.13'
    }
  }

  $launcher = Resolve-PythonLauncher
  if ($launcher) {
    return $launcher
  }

  throw 'Python 3.11+ was not found and automatic installation did not succeed.'
}

function Ensure-BackendVenv {
  param([hashtable]$PythonLauncher)

  if (Test-Path $backendPython) {
    return
  }

  Invoke-External -FilePath $PythonLauncher.FilePath -Arguments ($PythonLauncher.Arguments + @('-m', 'venv', '.venv')) -WorkingDirectory $backendRoot -Description 'Create backend virtual environment'
}

function Test-NeedsInstall {
  param(
    [string]$StampPath,
    [string[]]$SourcePaths
  )

  if (-not (Test-Path $StampPath)) {
    return $true
  }

  $stampTime = (Get-Item $StampPath).LastWriteTimeUtc
  foreach ($sourcePath in $SourcePaths) {
    if ((Get-Item $sourcePath).LastWriteTimeUtc -gt $stampTime) {
      return $true
    }
  }

  return $false
}

function Ensure-BackendDependencies {
  $sources = @(
    (Join-Path $backendRoot 'requirements.txt'),
    (Join-Path $backendRoot 'pyproject.toml')
  )

  if ($ReinstallBackend -or (Test-NeedsInstall -StampPath $backendStamp -SourcePaths $sources)) {
    Invoke-External -FilePath $backendPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') -WorkingDirectory $backendRoot -Description 'Upgrade backend pip'
    Invoke-External -FilePath $backendPython -Arguments @('-m', 'pip', 'install', '-r', 'requirements.txt') -WorkingDirectory $backendRoot -Description 'Install backend dependencies'
    New-Item -ItemType File -Path $backendStamp -Force | Out-Null
  }

  Invoke-External -FilePath $backendPython -Arguments @('-m', 'alembic', 'upgrade', 'head') -WorkingDirectory $backendRoot -Description 'Run database migrations'
  Invoke-External -FilePath $backendPython -Arguments @('scripts/bootstrap_admin.py') -WorkingDirectory $backendRoot -Description 'Bootstrap default admin (admin / Admin@123)'
}

function Ensure-FrontendDependencies {
  $sources = @(
    (Join-Path $frontendRoot 'package.json'),
    (Join-Path $frontendRoot 'package-lock.json')
  )

  if ($ReinstallFrontend -or -not (Test-Path (Join-Path $frontendRoot 'node_modules')) -or (Test-NeedsInstall -StampPath $frontendStamp -SourcePaths $sources)) {
    Invoke-External -FilePath 'npm' -Arguments @('install') -WorkingDirectory $frontendRoot -Description 'Install frontend dependencies'
    New-Item -ItemType File -Path $frontendStamp -Force | Out-Null
  }
}

function Initialize-LocalCelery {
  New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $brokerRoot 'in') -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $brokerRoot 'out') -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $brokerRoot 'processed') -Force | Out-Null

  $resultDb = (Join-Path $backendRoot 'celery_results.db') -replace '\\', '/'
  $env:REDIS_URL = 'filesystem://'
  $env:CELERY_RESULT_BACKEND = "db+sqlite:///$resultDb"
}

function Start-DetachedScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [Parameter(Mandatory = $true)]
    [string]$WorkingDirectory
  )

  Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-File', $ScriptPath
  ) -WorkingDirectory $WorkingDirectory | Out-Null
}

if (-not (Test-Path $backendRoot)) {
  throw "Backend directory not found: $backendRoot"
}

if (-not (Test-Path $frontendRoot)) {
  throw "Frontend directory not found: $frontendRoot"
}

foreach ($scriptPath in @($backendRunner, $workerRunner, $frontendRunner)) {
  if (-not (Test-Path $scriptPath)) {
    throw "Startup script not found: $scriptPath"
  }
}

New-Item -ItemType Directory -Path $bootstrapRoot -Force | Out-Null

$pythonLauncher = Ensure-Python
if ($pythonLauncher.Version -eq '3.13') {
  Write-Host 'Python 3.13 detected. If backend dependencies fail to install, the script will stop.' -ForegroundColor Yellow
}

Ensure-BackendVenv -PythonLauncher $pythonLauncher
Ensure-BackendDependencies
Ensure-FrontendDependencies
Initialize-LocalCelery

Write-Step 'Start backend API'
Start-DetachedScript -ScriptPath $backendRunner -WorkingDirectory $backendRoot

Write-Step 'Start Celery worker'
Start-DetachedScript -ScriptPath $workerRunner -WorkingDirectory $backendRoot

Write-Step 'Start frontend Vite dev server'
Start-DetachedScript -ScriptPath $frontendRunner -WorkingDirectory $frontendRoot

if (-not $NoBrowser) {
  Start-Sleep -Seconds 3
  Start-Process 'http://localhost:4173'
}

Write-Host 'Frontend URL: http://localhost:4173' -ForegroundColor Green
Write-Host 'Backend URL: http://localhost:8000' -ForegroundColor Green
Write-Host 'API docs: http://localhost:8000/docs' -ForegroundColor Green
Write-Host 'Celery uses a local filesystem queue. No external Redis is required.' -ForegroundColor Green
