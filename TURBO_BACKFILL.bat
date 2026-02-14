@echo off
echo ===========================================
echo TURBO BACKFILL - Maximum Speed Mode
echo ===========================================
echo.
echo This will:
echo   1. KILL ALL Python and Node processes
echo   2. FREE all ports (8787, 8788)
echo   3. Run backfill at MAXIMUM SPEED
echo.
echo Settings:
echo   Workers: 50
echo   Batch: 2000
echo   Sleep: 0.5s
echo.
echo WARNING: This will stop ALL trading systems!
echo.
pause
echo.
echo Starting aggressive cleanup and turbo backfill...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0turbo_backfill.ps1" -Workers 50 -Batch 2000 -Sleep 0.5

echo.
echo ===========================================
echo Process completed
echo ===========================================
pause
