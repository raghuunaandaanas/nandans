#!/usr/bin/env python3
"""
FAST BACKFILL SCRIPT - Holiday Mode
====================================
Purpose: Maximum speed backfilling for first closes database
Usage: Run when markets are closed (holidays/weekends) for full speed

Environment Variables (optional):
  FAST_WORKERS=50          # Number of parallel workers (default: 50)
  FAST_BATCH=2000          # Batch size per cycle (default: 2000)
  FAST_SLEEP=0.5           # Sleep between cycles in seconds (default: 0.5)
  FAST_LOOKBACK=5000       # Max days to look back (default: 5000)

Example:
  python fast_backfill.py
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

# Import from historyapp
import historyapp
from historyapp import (
    login, symbol_map,
    fetch_window_closes, db_get_history_batch, db_upsert_first_close, 
    db_update_history_state, init_db, load_symbols, OUT_DIR, log
)

# =============================================================================
# FAST BACKFILL CONFIGURATION
# =============================================================================

# Set environment variables for historyapp BEFORE importing
os.environ['CPU_PROFILE'] = 'max'
os.environ['HISTORY_FETCH_WORKERS'] = os.getenv('FAST_WORKERS', '50')
os.environ['HISTORY_BATCH'] = os.getenv('FAST_BATCH', '2000')
os.environ['HISTORY_SLEEP'] = os.getenv('FAST_SLEEP', '0.5')
os.environ['HISTORY_MAX_LOOKBACK_DAYS'] = os.getenv('FAST_LOOKBACK', '5000')
os.environ['HISTORY_WS_THROTTLE'] = '0'

FAST_WORKERS = int(os.getenv("FAST_WORKERS", "50"))
FAST_BATCH = int(os.getenv("FAST_BATCH", "2000"))
FAST_SLEEP = float(os.getenv("FAST_SLEEP", "0.5"))
FAST_LOOKBACK = int(os.getenv("FAST_LOOKBACK", "5000"))
MAX_RETRIES = 2  # Reduced retries for speed
EMPTY_STREAK_STOP = 10  # Stop earlier on empty streaks

print("=" * 70)
print("FAST BACKFILL - HOLIDAY MODE")
print("=" * 70)
print(f"Workers: {FAST_WORKERS}")
print(f"Batch Size: {FAST_BATCH}")
print(f"Sleep: {FAST_SLEEP}s")
print(f"Lookback: {FAST_LOOKBACK} days")
print("=" * 70)

# =============================================================================
# INITIALIZATION
# =============================================================================

# Load symbols first
symbol_map.update(load_symbols())
if not symbol_map:
    print("ERROR: No symbols found")
    sys.exit(1)

init_db()
login()

if not historyapp.rest_clients:
    print("ERROR: No REST clients available")
    sys.exit(1)

def split_round_robin(items, n):
    """Split items into n buckets round-robin style"""
    buckets = [[] for _ in range(n)]
    for i, item in enumerate(items):
        buckets[i % n].append(item)
    return buckets

def fetch_history_partition_fast(client, rows):
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

# =============================================================================
# MAIN BACKFILL LOOP
# =============================================================================

cycle = 0
start_time = time.time()

while True:
    cycle += 1
    batch = db_get_history_batch(FAST_BATCH)
    
    if not batch:
        print("\n" + "=" * 70)
        print("BACKFILL COMPLETED!")
        print("=" * 70)
        break
    
    valid_rows = [r for r in batch if symbol_map.get(r[0])]
    if not valid_rows:
        time.sleep(FAST_SLEEP)
        continue
    
    workers = min(FAST_WORKERS, len(valid_rows))
    buckets = split_round_robin(valid_rows, workers)
    
    processed = 0
    with_data = 0
    
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {}
        for i, bucket in enumerate(buckets):
            client = historyapp.rest_clients[i % len(historyapp.rest_clients)]
            fut_map[pool.submit(fetch_history_partition_fast, client, bucket)] = bucket
        
        for fut in as_completed(fut_map):
            try:
                part_results = fut.result()
            except Exception as e:
                print(f"Partition error: {e}")
                part_results = []
            
            for row, vals, fetched in part_results:
                processed += 1
                symbol, next_day_s, empty_streak, lookback_days, retries = row
                info = symbol_map[symbol]
                
                day_obj = date.fromisoformat(next_day_s)
                next_day_new = (day_obj - timedelta(days=1)).isoformat()
                
                if fetched:
                    db_upsert_first_close(symbol, info, next_day_s, vals, True)
                    has_data = bool(
                        vals
                        and (
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
                    if retries >= MAX_RETRIES:
                        retries = 0
                        lookback_days += 1
                        empty_streak += 1
                    else:
                        next_day_new = next_day_s
                
                done = lookback_days >= FAST_LOOKBACK or empty_streak >= EMPTY_STREAK_STOP
                db_update_history_state(symbol, next_day_new, empty_streak, lookback_days, retries, done)
    
    # Progress stats
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0
    
    # Get remaining count
    import sqlite3
    with sqlite3.connect(OUT_DIR / "first_closes.db") as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM history_state WHERE done=0")
        remaining = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM history_state")
        total = cursor.fetchone()[0]
    
    done_count = total - remaining
    progress = (done_count / total * 100) if total > 0 else 0
    eta_secs = remaining / rate if rate > 0 else 0
    eta_hours = eta_secs / 3600
    
    print(f"[Cycle {cycle}] Processed: {processed}, With data: {with_data}, "
          f"Progress: {done_count}/{total} ({progress:.2f}%), "
          f"Rate: {rate:.1f} symbols/sec, ETA: {eta_hours:.1f}h")
    
    time.sleep(FAST_SLEEP)

print(f"\nTotal time: {(time.time() - start_time) / 3600:.2f} hours")


def split_round_robin(items, n):
    """Split items into n buckets round-robin style"""
    buckets = [[] for _ in range(n)]
    for i, item in enumerate(items):
        buckets[i % n].append(item)
    return buckets
