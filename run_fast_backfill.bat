@echo off
echo ===========================================
echo FAST BACKFILL - Holiday Mode
echo ===========================================
echo.
echo This will STOP the normal historyapp and
echo run MAXIMUM SPEED backfill for holidays.
echo.
echo Configuration:
echo   Workers: 50
echo   Batch: 2000
echo   Sleep: 0.5s
echo.
pause

echo.
echo [1/3] Stopping historyapp...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *historyapp*" 2>nul
taskkill /F /IM python.exe /FI "COMMANDLINE eq *historyapp*" 2>nul

echo [2/3] Stopping node UI...
taskkill /F /IM node.exe 2>nul

timeout /t 2 /nobreak >nul

echo [3/3] Starting FAST backfill...
echo.
python fast_backfill.py

echo.
echo Backfill complete! Restart normal app with:
echo   python start_all.py
echo.
pause
