@echo off
echo ===========================================
echo TURBO BACKFILL MODE
echo ===========================================
echo.
echo This will STOP the normal app and run
echo MAXIMUM SPEED backfill using environment
echo variables.
echo.
echo Settings:
echo   HISTORY_FETCH_WORKERS=50
echo   HISTORY_BATCH=2000  
echo   HISTORY_SLEEP=0.5
echo.
pause

echo.
echo [1/3] Stopping all processes...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 3 /nobreak >nul

echo [2/3] Setting turbo environment variables...
set CPU_PROFILE=max
set HISTORY_FETCH_WORKERS=50
set HISTORY_BATCH=2000
set HISTORY_SLEEP=0.5
set FIRST_CLOSE_WORKERS=50
set HISTORY_WS_THROTTLE=0

echo [3/3] Starting turbo backfill...
echo.
echo Progress will be logged to console.
echo Press Ctrl+C to stop (data is saved continuously)
echo.

python historyapp.py

echo.
echo ===========================================
echo Backfill stopped or completed!
echo ===========================================
echo Restart normal operation with:
echo   python start_all.py
echo.
pause
