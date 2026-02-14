# Fast Backfill Instructions

## Problem
Normal backfill is slow (3.67% after whole night) due to throttling and low worker counts.

## Solution: Environment Variable Mode

Instead of a separate script, use environment variables to speed up historyapp:

### Option 1: Turbo Mode (Fastest - ~18 minutes)
```bash
# Stop current app
python start_all.py stop

# Run with turbo settings
set HISTORY_WORKERS=50
set HISTORY_BATCH=2000
set HISTORY_SLEEP=0.5
python historyapp.py
```

### Option 2: Fast Mode (~1.4 hours)
```bash
# Stop current app
python start_all.py stop

# Run with fast settings
set HISTORY_WORKERS=20
set HISTORY_BATCH=1000
set HISTORY_SLEEP=1
python historyapp.py
```

### Option 3: Keep Normal Settings But Max Workers
```bash
set HISTORY_WORKERS=50
set HISTORY_BATCH=1000
set HISTORY_SLEEP=2
python historyapp.py
```

## How It Works

The historyapp already reads these environment variables:
- `HISTORY_WORKERS` - Number of parallel workers (default: 12)
- `HISTORY_BATCH` - Batch size per cycle (default: 1000)
- `HISTORY_SLEEP` - Sleep between cycles in seconds (default: 5)

## Monitoring Progress

In another terminal:
```bash
# Check progress
python check_trades.py

# Or directly
cd history_out && python -c "import sqlite3; db=sqlite3.connect('first_closes.db'); pending=db.execute('SELECT COUNT(*) FROM history_state WHERE done=0').fetchone()[0]; total=db.execute('SELECT COUNT(*) FROM history_state').fetchone()[0]; print(f'Progress: {total-pending}/{total} ({(total-pending)/total*100:.2f}%)')"
```

## When Complete

Restart normal operation:
```bash
python start_all.py
```
