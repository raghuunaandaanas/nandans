#!/usr/bin/env python3
"""
HISTORY BACKFILL - Dedicated History Download
==============================================
Single purpose: Backfill historical first closes at maximum speed.
NO WebSocket, NO today fetch, just pure history backfill.

Usage:
    python history_backfill.py              # Interactive
    python history_backfill.py --yes        # Skip confirmation
"""

import os
import sys
import time
import subprocess
import sqlite3
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Force max performance mode
os.environ['CPU_PROFILE'] = 'max'
os.environ['HISTORY_FETCH_WORKERS'] = '50'
os.environ['HISTORY_BATCH'] = '2000'
os.environ['HISTORY_SLEEP'] = '0.5'
os.environ['HISTORY_MAX_LOOKBACK_DAYS'] = '5000'
os.environ['MAX_REST_SESSIONS'] = '8'
os.environ['FIRST_CLOSE_MAX_RETRIES'] = '2'

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Import historyapp module
import historyapp
from historyapp import (
    load_symbols, symbol_map,
    fetch_window_closes, init_db, login,
    HISTORY_BATCH, HISTORY_SLEEP_SEC, HISTORY_FETCH_WORKERS,
    MAX_FETCH_RETRIES, HISTORY_MAX_LOOKBACK_DAYS
)

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = Path(__file__).parent / "history_out" / "first_closes.db"
EMPTY_STREAK_STOP = 10  # Stop after 10 empty days

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def kill_all():
    """Kill all Python and Node processes (except self)"""
    log("Killing all processes...")
    import os
    my_pid = os.getpid()
    
    # Kill other Python processes
    try:
        result = subprocess.run('wmic process where "name=\'python.exe\'" get ProcessId', 
                               shell=True, capture_output=True, text=True)
        for line in result.stdout.strip().split('\n')[1:]:
            try:
                pid = int(line.strip())
                if pid != my_pid:
                    subprocess.run(f"taskkill /F /PID {pid} 2>nul", shell=True, capture_output=True)
            except:
                pass
    except:
        pass
    
    # Kill Node
    subprocess.run("taskkill /F /IM node.exe /T 2>nul", shell=True, capture_output=True)
    time.sleep(2)
    log("All processes killed")

def split_round_robin(items, n):
    """Split items into n buckets round-robin style"""
    buckets = [[] for _ in range(n)]
    for i, item in enumerate(items):
        buckets[i % n].append(item)
    return [b for b in buckets if b]

def fetch_history_partition(client, rows):
    """Fetch history for a partition of rows"""
    results = []
    for row in rows:
        symbol, next_day_s, empty_streak, lookback_days, retries = row
        info = symbol_map.get(symbol)
        if not info:
            results.append((row, {}, False))
            continue
        
        day_obj = date.fromisoformat(next_day_s)
        vals, fetched = fetch_window_closes(client, info["exchange"], info["token"], day_obj)
        results.append((row, vals, fetched))
    return results

def get_progress():
    """Get current backfill progress"""
    try:
        db = sqlite3.connect(DB_PATH)
        db.execute("PRAGMA busy_timeout = 5000")
        total = db.execute("SELECT COUNT(*) FROM history_state").fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM history_state WHERE done=1").fetchone()[0]
        pending = db.execute("SELECT COUNT(*) FROM history_state WHERE done=0").fetchone()[0]
        db.close()
        return {'total': total, 'done': done, 'pending': pending, 'percent': (done/total*100) if total else 0}
    except Exception as e:
        print(f"Error getting progress: {e}")
        return None

def main():
    print("=" * 70)
    print("HISTORY BACKFILL - Dedicated Mode")
    print("=" * 70)
    print(f"Workers: {HISTORY_FETCH_WORKERS}")
    print(f"Batch: {HISTORY_BATCH}")
    print(f"Sleep: {HISTORY_SLEEP_SEC}s")
    print("=" * 70)
    print()
    
    # Check if should kill
    if '--yes' in sys.argv or '-y' in sys.argv:
        kill_all()
    else:
        resp = input("Kill all other processes? (yes/no): ")
        if resp.lower() == 'yes':
            kill_all()
    
    # Initialize
    log("Initializing...")
    symbol_map.update(load_symbols())
    if not symbol_map:
        print("ERROR: No symbols found")
        return
    
    # Don't call init_db() - it creates a global connection that locks the DB
    # init_db()
    
    # Login to get REST clients
    try:
        login()
    except Exception as e:
        print(f"ERROR: Login failed: {e}")
        return
    
    if not historyapp.rest_clients:
        print("ERROR: No REST clients available")
        return
    
    log(f"REST sessions: {len(historyapp.rest_clients)}")
    log(f"Symbols loaded: {len(symbol_map)}")
    
    # Create our own DB connection (single connection for everything)
    log("Opening database connection...")
    import sqlite3
    db_conn = sqlite3.connect(DB_PATH)
    db_conn.execute("PRAGMA busy_timeout = 10000")
    
    # Show starting progress
    log("Getting progress...")
    total = db_conn.execute("SELECT COUNT(*) FROM history_state").fetchone()[0]
    done = db_conn.execute("SELECT COUNT(*) FROM history_state WHERE done=1").fetchone()[0]
    pending = total - done
    percent = (done/total*100) if total else 0
    log(f"Starting: {done}/{total} ({percent:.2f}%)")
    
    print()
    print("=" * 70)
    log("Backfill started - Press Ctrl+C to stop")
    print("=" * 70)
    print()
    
    def get_batch(limit):
        cur = db_conn.execute(
            "SELECT symbol, next_day, empty_streak, lookback_days, retries FROM history_state WHERE done = 0 ORDER BY retries ASC, next_day DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()
    
    # Main backfill loop
    cycle = 0
    start_time = time.time()
    
    log("Starting main backfill loop...")
    
    try:
        while True:
            cycle += 1
            if cycle % 100 == 1:
                log(f"Cycle {cycle} - fetching batch...")
            batch = get_batch(HISTORY_BATCH)
            
            if not batch:
                log("BACKFILL COMPLETED!")
                break
            
            valid_rows = [r for r in batch if symbol_map.get(r[0])]
            if not valid_rows:
                time.sleep(HISTORY_SLEEP_SEC)
                continue
            
            # Use all available REST clients
            workers = min(HISTORY_FETCH_WORKERS, len(historyapp.rest_clients), len(valid_rows))
            buckets = split_round_robin(valid_rows, workers)
            
            processed = 0
            with_data = 0
            
            with ThreadPoolExecutor(max_workers=workers) as pool:
                fut_map = {}
                for i, bucket in enumerate(buckets):
                    client = historyapp.rest_clients[i % len(historyapp.rest_clients)]
                    fut_map[pool.submit(fetch_history_partition, client, bucket)] = bucket
                
                for fut in as_completed(fut_map):
                    try:
                        part_results = fut.result()
                    except Exception as e:
                        log(f"Partition error: {e}")
                        part_results = []
                    
                    for row, vals, fetched in part_results:
                        processed += 1
                        symbol, next_day_s, empty_streak, lookback_days, retries = row
                        info = symbol_map[symbol]
                        
                        day_obj = date.fromisoformat(next_day_s)
                        next_day_new = (day_obj - timedelta(days=1)).isoformat()
                        
                        if fetched:
                            # Upsert first close
                            db_conn.execute("""
                                INSERT INTO first_closes(symbol, day, exchange, token, tsym, first_1m_close, first_5m_close, first_15m_close, fetch_done, updated_at)
                                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                                ON CONFLICT(symbol, day) DO UPDATE SET
                                    first_1m_close=excluded.first_1m_close,
                                    first_5m_close=excluded.first_5m_close,
                                    first_15m_close=excluded.first_15m_close,
                                    fetch_done=excluded.fetch_done,
                                    updated_at=excluded.updated_at
                            """, (symbol, next_day_s, info['exchange'], info['token'], info['tsym'],
                                  vals.get('first_1m_close'), vals.get('first_5m_close'), vals.get('first_15m_close'), 1))
                            db_conn.commit()
                            
                            has_data = bool(
                                vals and (
                                    vals.get("first_1m_close") is not None
                                    or vals.get("first_5m_close") is not None
                                    or vals.get("first_15m_close") is not None
                                )
                            )
                            empty_streak = 0 if has_data else empty_streak + 1
                            lookback_days += 1
                            retries = 0
                            if has_data:
                                with_data += 1
                        else:
                            retries += 1
                            if retries >= MAX_FETCH_RETRIES:
                                retries = 0
                                lookback_days += 1
                                empty_streak += 1
                            else:
                                next_day_new = next_day_s
                        
                        done = lookback_days >= HISTORY_MAX_LOOKBACK_DAYS or empty_streak >= EMPTY_STREAK_STOP
                        
                        # Update history state
                        db_conn.execute("""
                            UPDATE history_state
                            SET next_day=?, empty_streak=?, lookback_days=?, retries=?, done=?, updated_at=datetime('now')
                            WHERE symbol=?
                        """, (next_day_new, empty_streak, lookback_days, retries, 1 if done else 0, symbol))
                        db_conn.commit()
            
            # Progress report every 10 cycles
            if cycle % 10 == 0:
                elapsed = time.time() - start_time
                progress = get_progress()
                if progress:
                    rate = progress['done'] / elapsed if elapsed > 0 else 0
                    eta = progress['pending'] / rate / 3600 if rate > 0 else 0
                    log(f"Progress: {progress['done']}/{progress['total']} ({progress['percent']:.2f}%) | "
                        f"Rate: {rate:.1f} sym/s | ETA: {eta:.1f}h")
            
            time.sleep(HISTORY_SLEEP_SEC)
            
    except KeyboardInterrupt:
        log("Stopped by user")
    finally:
        db_conn.close()
    
    # Final stats
    print()
    print("=" * 70)
    progress = get_progress()
    if progress:
        log(f"Final: {progress['done']}/{progress['total']} ({progress['percent']:.2f}%)")
    elapsed = time.time() - start_time
    log(f"Total time: {elapsed/3600:.2f} hours")
    print("=" * 70)
    print()
    print("Restart normal operation: python start_all.py")

if __name__ == "__main__":
    main()
