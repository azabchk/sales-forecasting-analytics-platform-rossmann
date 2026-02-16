[CmdletBinding()]
param(
  [string]$BackendHost = "0.0.0.0",
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

& (Join-Path $PSScriptRoot "stop_local_windows.ps1") | Out-Null

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  $nodePath = "C:\Program Files\nodejs"
  if (Test-Path $nodePath) {
    $env:Path = "$nodePath;$env:Path"
  }
}

$backendPy = Resolve-Path "backend\.venv311\Scripts\python.exe" -ErrorAction Stop
$frontendDir = Resolve-Path "frontend" -ErrorAction Stop
$backendDir = Resolve-Path "backend" -ErrorAction Stop

$backendLog = Join-Path $repoRoot "backend_run.log"
$frontendLog = Join-Path $repoRoot "frontend_run.log"

$backendCmd = "cd /d `"$backendDir`" && `"$backendPy`" -m uvicorn app.main:app --host $BackendHost --port $BackendPort > `"$backendLog`" 2>&1"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $backendCmd -WindowStyle Hidden | Out-Null

$frontendCmd = "cd /d `"$frontendDir`" && set PATH=C:\Program Files\nodejs;%PATH% && npm run dev > `"$frontendLog`" 2>&1"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $frontendCmd -WindowStyle Hidden | Out-Null

$backendReady = $false
$frontendReady = $false
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 2

  if (-not $backendReady) {
    try {
      $null = Invoke-WebRequest -UseBasicParsing "http://localhost:$BackendPort/api/v1/health" -TimeoutSec 3
      $backendReady = $true
    }
    catch {}
  }

  if (-not $frontendReady) {
    try {
      $null = Invoke-WebRequest -UseBasicParsing "http://localhost:$FrontendPort" -TimeoutSec 3
      $frontendReady = $true
    }
    catch {}
  }

  if ($backendReady -and $frontendReady) {
    break
  }
}

if (-not $backendReady) {
  Write-Error "Backend did not become ready. Check backend_run.log"
}
if (-not $frontendReady) {
  Write-Error "Frontend did not become ready. Check frontend_run.log"
}

Write-Host "Backend:  http://localhost:$BackendPort/docs" -ForegroundColor Green
Write-Host "Frontend: http://localhost:$FrontendPort" -ForegroundColor Green
