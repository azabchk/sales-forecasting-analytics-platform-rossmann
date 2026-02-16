@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Bootstrapping environment (DB init, ETL, ML training)...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\bootstrap_local_windows.ps1"
if errorlevel 1 goto :fail

echo [2/3] Starting backend + frontend...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start_local_windows.ps1"
if errorlevel 1 goto :fail

echo [3/3] Checking status...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\status_local_windows.ps1"
if errorlevel 1 goto :fail

echo.
echo Project is running.
echo Frontend: http://localhost:5173
echo Backend docs: http://localhost:8000/docs
exit /b 0

:fail
echo.
echo Run failed. Check backend_run.log and frontend_run.log for details.
exit /b 1
