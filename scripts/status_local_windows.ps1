[CmdletBinding()]
param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

try {
  $health = Invoke-WebRequest -UseBasicParsing "http://localhost:$BackendPort/api/v1/health" -TimeoutSec 3
  Write-Host "Backend healthy: $($health.Content)" -ForegroundColor Green
}
catch {
  Write-Host "Backend is not reachable on port $BackendPort" -ForegroundColor Yellow
}

try {
  $front = Invoke-WebRequest -UseBasicParsing "http://localhost:$FrontendPort" -TimeoutSec 3
  Write-Host "Frontend reachable on http://localhost:$FrontendPort (HTTP $($front.StatusCode))" -ForegroundColor Green
}
catch {
  Write-Host "Frontend is not reachable on port $FrontendPort" -ForegroundColor Yellow
}
