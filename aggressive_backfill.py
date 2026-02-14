#!/usr/bin/env python3
"""
AGGRESSIVE BACKFILL - Kills everything and runs max speed
============================================================
Usage: python aggressive_backfill.py
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

# =============================================================================
# STEP 1: KILL ALL PROCESSES
# =============================================================================
print("=" * 70)
print("AGGRESSIVE BACKFILL - Maximum Speed Mode")
print("=" * 70)
print()
print("[1/5] Killing all processes...")

# Kill Python
subprocess.run("taskkill /F /IM python.exe /T 2>nul", shell=True, capture_output=True)
subprocess.run("taskkill /F /IM pythonw.exe /T 2>nul", shell=True, capture_output=True)

# Kill Node
subprocess.run("taskkill /F /IM node.exe /T 2>nul", shell=True, capture_output=True)

# Kill CMD windows with specific titles
subprocess.run('taskkill /F /FI "WINDOWTITLE eq *history*" 2>nul', shell=True, capture_output=True)
subprocess.run('taskkill /F /FI "WINDOWTITLE eq *crypto*" 2>nul', shell=True, capture_output=True)

time.sleep(2)
print("  [OK] All processes killed")

# =============================================================================
# STEP 2: FREE PORTS
# =============================================================================
print()
print("[2/5] Freeing ports...")

# Use netstat to find and kill processes on ports 8787 and 8788
try:
    result = subprocess.run("netstat -ano | findstr ':8787'", shell=True, capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'LISTENING' in line:
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                subprocess.run(f"taskkill /F /PID {pid} 2>nul", shell=True, capture_output=True)
except:
    pass

try:
    result = subprocess.run("netstat -ano | findstr ':8788'", shell=True, capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'LISTENING' in line:
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                subprocess.run(f"taskkill /F /PID {pid} 2>nul", shell=True, capture_output=True)
except:
    pass

print("  [OK] Ports freed")

# =============================================================================
# STEP 3: SET ENVIRONMENT VARIABLES
# =============================================================================
print()
print("[3/5] Setting maximum speed configuration...")

os.environ['CPU_PROFILE'] = 'max'
os.environ['HISTORY_FETCH_WORKERS'] = '50'
os.environ['HISTORY_BATCH'] = '2000'
os.environ['HISTORY_SLEEP'] = '0.5'
os.environ['HISTORY_MAX_LOOKBACK_DAYS'] = '5000'
os.environ['HISTORY_WS_THROTTLE'] = '0'
os.environ['TODAY_FETCH_WORKERS'] = '50'
os.environ['MAX_REST_SESSIONS'] = '8'
os.environ['FIRST_CLOSE_MAX_RETRIES'] = '2'

print(f"  CPU_PROFILE = {os.environ['CPU_PROFILE']}")
print(f"  HISTORY_FETCH_WORKERS = {os.environ['HISTORY_FETCH_WORKERS']}")
print(f"  HISTORY_BATCH = {os.environ['HISTORY_BATCH']}")
print(f"  HISTORY_SLEEP = {os.environ['HISTORY_SLEEP']}")
print(f"  HISTORY_WS_THROTTLE = {os.environ['HISTORY_WS_THROTTLE']}")
print("  [OK] Configuration set")

# =============================================================================
# STEP 4: CLEANUP TEMP FILES
# =============================================================================
print()
print("[4/5] Cleaning up temp files...")

# Remove WAL and SHM files that might cause locks
for ext in ['*.db-shm', '*.db-wal']:
    for f in Path('history_out').glob(ext):
        try:
            f.unlink()
            print(f"  Removed {f.name}")
        except:
            pass

print("  [OK] Cleanup complete")

# =============================================================================
# STEP 5: START BACKFILL
# =============================================================================
print()
print("[5/5] Starting turbo backfill...")
print("=" * 70)
print()
print("Press Ctrl+C to stop (progress saves automatically)")
print()

# Show initial progress
try:
    import sqlite3
    db = sqlite3.connect('history_out/first_closes.db')
    done = db.execute("SELECT COUNT(*) FROM history_state WHERE done=1").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM history_state").fetchone()[0]
    print(f"Starting progress: {done}/{total} ({done/total*100:.2f}%)")
    db.close()
except Exception as e:
    print(f"Could not read initial progress: {e}")

print()

# Run historyapp
try:
    subprocess.run([sys.executable, "historyapp.py"])
except KeyboardInterrupt:
    print("\n\nBackfill interrupted by user")

# Show final progress
print()
print("=" * 70)
print("BACKFILL STOPPED")
print("=" * 70)
print()

try:
    import sqlite3
    db = sqlite3.connect('history_out/first_closes.db')
    done = db.execute("SELECT COUNT(*) FROM history_state WHERE done=1").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM history_state").fetchone()[0]
    print(f"Final progress: {done}/{total} ({done/total*100:.2f}%)")
    db.close()
except:
    pass

print()
print("Restart normal operation with: python start_all.py")
print()
input("Press Enter to exit...")
