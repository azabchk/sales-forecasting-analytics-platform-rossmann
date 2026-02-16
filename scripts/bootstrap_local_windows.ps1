[CmdletBinding()]
param(
  [string]$PyVersion = "3.11",
  [string]$PostgresSuperUser = "postgres",
  [string]$PostgresSuperPassword = "postgres",
  [string]$DbUser = "rossmann_user",
  [string]$DbPassword = "change_me",
  [string]$DbName = "rossmann",
  [string]$DbHost = "127.0.0.1",
  [int]$DbPort = 5432
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot
$env:PYTHONIOENCODING = "utf-8"

function Get-PsqlPath {
  $cmd = Get-Command psql.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe",
    "C:\Program Files\PostgreSQL\14\bin\psql.exe"
  )

  foreach ($path in $candidates) {
    if (Test-Path $path) { return $path }
  }

  throw "psql.exe was not found. Install PostgreSQL and retry."
}

function Ensure-Venv {
  param(
    [Parameter(Mandatory = $true)][string]$VenvPath,
    [Parameter(Mandatory = $true)][string]$RequirementsPath,
    [Parameter(Mandatory = $true)][string]$Version
  )

  if (-not (Test-Path (Join-Path $VenvPath "Scripts\python.exe"))) {
    & py "-$Version" -m venv $VenvPath
  }

  $py = Join-Path $VenvPath "Scripts\python.exe"
  & $py -m pip install --upgrade pip
  & $py -m pip install -r $RequirementsPath
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Python launcher 'py' is not available. Install Python 3.11+ first."
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  $nodePath = "C:\Program Files\nodejs"
  if (Test-Path $nodePath) {
    $env:Path = "$nodePath;$env:Path"
  }
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js is not available. Install Node.js LTS first."
}

$psql = Get-PsqlPath

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

$escapedDbPassword = $DbPassword.Replace("'", "''")

$env:PGPASSWORD = $PostgresSuperPassword
& $psql -h $DbHost -p $DbPort -U $PostgresSuperUser -d postgres -v ON_ERROR_STOP=1 -c "SELECT 1;" | Out-Null

$roleExists = & $psql -h $DbHost -p $DbPort -U $PostgresSuperUser -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DbUser'"
if (-not $roleExists) {
  & $psql -h $DbHost -p $DbPort -U $PostgresSuperUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE $DbUser LOGIN PASSWORD '$escapedDbPassword';"
}

$dbExists = & $psql -h $DbHost -p $DbPort -U $PostgresSuperUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'"
if (-not $dbExists) {
  & $psql -h $DbHost -p $DbPort -U $PostgresSuperUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DbName OWNER $DbUser;"
}

Ensure-Venv -VenvPath "etl\.venv311" -RequirementsPath "etl\requirements.txt" -Version $PyVersion
Ensure-Venv -VenvPath "ml\.venv311" -RequirementsPath "ml\requirements.txt" -Version $PyVersion
Ensure-Venv -VenvPath "backend\.venv311" -RequirementsPath "backend\requirements.txt" -Version $PyVersion

cmd /c "cd /d frontend && npm install"

$etlPy = (Resolve-Path "etl\.venv311\Scripts\python.exe").Path
$mlPy = (Resolve-Path "ml\.venv311\Scripts\python.exe").Path

& $etlPy "scripts\init_db.py"

Push-Location "etl"
& $etlPy "etl_load.py" --config "config.yaml"
& $etlPy "data_quality.py" --config "config.yaml"
Pop-Location

Push-Location "ml"
& $mlPy "train.py" --config "config.yaml"
& $mlPy "evaluate.py" --config "config.yaml"
Pop-Location

Write-Host "Bootstrap completed successfully." -ForegroundColor Green
Write-Host "Next: run scripts\start_local_windows.ps1" -ForegroundColor Green
