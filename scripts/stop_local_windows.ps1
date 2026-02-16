[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$targets = Get-CimInstance Win32_Process | Where-Object {
  ($_.CommandLine -match "uvicorn app.main:app") -or
  ($_.CommandLine -match "vite(\.js)?") -or
  ($_.CommandLine -match "npm run dev")
}

if (-not $targets) {
  Write-Host "No backend/frontend processes found." -ForegroundColor Yellow
  exit 0
}

$pids = @($targets | Select-Object -ExpandProperty ProcessId)
foreach ($procId in $pids) {
  try {
    Stop-Process -Id $procId -Force -ErrorAction Stop
  }
  catch {
    Write-Warning "Failed to stop PID ${procId}: $($_.Exception.Message)"
  }
}

Write-Host "Stopped processes: $($pids -join ', ')" -ForegroundColor Green
