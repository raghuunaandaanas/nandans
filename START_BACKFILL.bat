@echo off
echo ===========================================
echo HISTORY BACKFILL - Holiday Mode
echo ===========================================
echo.

REM Kill any existing Python processes
echo Stopping existing processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul
timeout /t 3 /nobreak >nul

REM Clean up WAL files
cd /d "%~dp0\history_out"
del /F *.db-shm *.db-wal 2>nul

cd /d "%~dp0"

REM Set environment for maximum speed
set CPU_PROFILE=max
set HISTORY_FETCH_WORKERS=50
set HISTORY_BATCH=2000
set HISTORY_SLEEP=0.5
set HISTORY_WS_THROTTLE=0
set MAX_REST_SESSIONS=8

echo.
echo Starting backfill with settings:
echo   Workers: 50
echo   Batch: 2000
echo   Sleep: 0.5s
echo.
echo Press Ctrl+C to stop (progress saves automatically)
echo.

python -u backfill.py --turbo --yes

echo.
echo ===========================================
echo Backfill stopped
echo ===========================================
echo.
echo Check status: python backfill.py --status
echo Restart: python start_all.py
echo.
pause
