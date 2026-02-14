@echo off
echo ===========================================
echo BACKFILL PROGRESS MONITOR
echo ===========================================
echo.
echo Press Ctrl+C to stop monitoring
echo (this won't stop the backfill)
echo.
timeout /t 2 /nobreak >nul

:loop
cls
echo ===========================================
echo BACKFILL PROGRESS - %date% %time%
echo ===========================================
echo.

cd /d "%~dp0\history_out"

sqlite3 first_closes.db "SELECT 
  'Total: ' || total || ' | Done: ' || done || ' | Pending: ' || pending || ' | Progress: ' || ROUND(done*100.0/total,2) || '%' as status
FROM (
  SELECT 
    (SELECT COUNT(*) FROM history_state) as total,
    (SELECT COUNT(*) FROM history_state WHERE done=1) as done,
    (SELECT COUNT(*) FROM history_state WHERE done=0) as pending
);"

echo.
sqlite3 first_closes.db "SELECT 
  '1m closed: ' || COUNT(*) 
FROM first_closes 
WHERE first_1m_close IS NOT NULL;"

sqlite3 first_closes.db "SELECT 
  '5m closed: ' || COUNT(*) 
FROM first_closes 
WHERE first_5m_close IS NOT NULL;"

sqlite3 first_closes.db "SELECT 
  '15m closed: ' || COUNT(*) 
FROM first_closes 
WHERE first_15m_close IS NOT NULL;"

echo.
echo ===========================================
echo Refreshing in 5 seconds...
echo ===========================================
timeout /t 5 /nobreak >nul
goto loop
