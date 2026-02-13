@echo off
cd /d D:\history

REM Speed settings for backfill (set CPU_PROFILE=max for maximum speed)
set CPU_PROFILE=max
set MAX_REST_SESSIONS=8
set TODAY_FETCH_WORKERS=8
set HISTORY_FETCH_WORKERS=16
set CURRENT_DAY_BATCH=1200
set CURRENT_DAY_SLEEP=1
set HISTORY_BATCH=1000
set HISTORY_SLEEP=1

python app_start.py start --clean
