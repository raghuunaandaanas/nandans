#!/usr/bin/env python3
"""
BACKFILL - Historical Data Download (Holiday Mode)
==================================================
Single script to backfill first closes at maximum speed.

Usage:
    python backfill.py          # Interactive mode
    python backfill.py --turbo  # Maximum speed (kills all, uses all resources)
    python backfill.py --fast   # Fast but keeps other systems running
    python backfill.py --status # Show progress only

Modes:
    --turbo  : Kills everything, uses 50 workers, completes in ~20 min
    --fast   : Uses 20 workers, doesn't kill other systems
    --eco    : Default, uses 4 workers (slow but safe)
"""

import os
import sys
import time
import subprocess
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = Path(__file__).parent / "history_out" / "first_closes.db"

MODES = {
    'eco':   {'workers': 4,  'batch': 500,  'sleep': 5.0,  'kill': False, 'profile': 'eco'},
    'fast':  {'workers': 20, 'batch': 1000, 'sleep': 1.0,  'kill': False, 'profile': 'max'},
    'turbo': {'workers': 50, 'batch': 2000, 'sleep': 0.5,  'kill': True,  'profile': 'max'},
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def kill_all():
    """Kill all Python and Node processes aggressively (except this one)"""
    log("Killing all Python and Node processes...")
    
    import os
    my_pid = os.getpid()
    
    # Get list of Python PIDs first (excluding self)
    try:
        result = subprocess.run("tasklist /FI \"IMAGENAME eq python.exe\" /FO CSV /NH", shell=True, capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if 'python.exe' in line:
                parts = line.split('","')
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        if pid != my_pid:
                            subprocess.run(f"taskkill /F /PID {pid} 2>nul", shell=True, capture_output=True)
                    except:
                        pass
    except:
        pass
    
    # Kill Node processes
    subprocess.run("taskkill /F /IM node.exe /T 2>nul", shell=True, capture_output=True)
    
    # Kill processes on ports
    try:
        result = subprocess.run("netstat -ano | findstr ':8787 :8788'", shell=True, capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid != str(my_pid):
                        subprocess.run(f"taskkill /F /PID {pid} 2>nul", shell=True, capture_output=True)
    except:
        pass
    
    time.sleep(2)
    log("All processes killed")

def clean_temp_files():
    """Remove WAL/SHM files that might cause locks"""
    for ext in ['*.db-shm', '*.db-wal']:
        for f in Path(__file__).parent.glob(f'history_out/{ext}'):
            try:
                f.unlink()
            except:
                pass

def get_progress():
    """Get current backfill progress"""
    if not DB_PATH.exists():
        return None
    try:
        db = sqlite3.connect(DB_PATH)
        total = db.execute("SELECT COUNT(*) FROM history_state").fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM history_state WHERE done=1").fetchone()[0]
        db.close()
        return {'total': total, 'done': done, 'pending': total - done, 'percent': (done/total*100) if total else 0}
    except:
        return None

def show_status():
    """Show current backfill status"""
    progress = get_progress()
    if not progress:
        print("No database found or database is empty")
        return
    
    print("=" * 60)
    print("BACKFILL STATUS")
    print("=" * 60)
    print(f"Total symbols:    {progress['total']:,}")
    print(f"Completed:        {progress['done']:,}")
    print(f"Pending:          {progress['pending']:,}")
    print(f"Progress:         {progress['percent']:.2f}%")
    print()
    
    # Estimate time at different speeds
    pending = progress['pending']
    print(f"ETA at current speed (0.2/s): {pending/0.2/3600:.1f} hours")
    print(f"ETA at fast speed (10/s):     {pending/10/3600:.1f} hours")
    print(f"ETA at turbo speed (50/s):    {pending/50/3600:.1f} hours")

def set_env(mode_config):
    """Set environment variables for backfill"""
    os.environ['CPU_PROFILE'] = mode_config['profile']
    os.environ['HISTORY_FETCH_WORKERS'] = str(mode_config['workers'])
    os.environ['HISTORY_BATCH'] = str(mode_config['batch'])
    os.environ['HISTORY_SLEEP'] = str(mode_config['sleep'])
    os.environ['HISTORY_WS_THROTTLE'] = '0'
    os.environ['TODAY_FETCH_WORKERS'] = str(mode_config['workers'])
    os.environ['MAX_REST_SESSIONS'] = '8'
    
    log(f"Mode: {mode_config['profile'].upper()}")
    log(f"Workers: {mode_config['workers']}, Batch: {mode_config['batch']}, Sleep: {mode_config['sleep']}s")

def run_backfill():
    """Run the historyapp for backfill"""
    log("Starting backfill...")
    log("Press Ctrl+C to stop (progress saves automatically)")
    print()
    
    # Show starting progress
    progress = get_progress()
    if progress:
        log(f"Starting: {progress['done']}/{progress['total']} ({progress['percent']:.2f}%)")
    
    print("=" * 60)
    
    # Run historyapp
    try:
        subprocess.run([sys.executable, "historyapp.py"], cwd=Path(__file__).parent)
    except KeyboardInterrupt:
        print("\n")
        log("Backfill interrupted by user")
    
    # Show final progress
    print()
    print("=" * 60)
    progress = get_progress()
    if progress:
        log(f"Final: {progress['done']}/{progress['total']} ({progress['percent']:.2f}%)")
    
    print()
    print("Restart normal operation:")
    print("  python start_all.py")

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Backfill historical data')
    parser.add_argument('--turbo', action='store_true', help='Maximum speed (kills all, ~20 min)')
    parser.add_argument('--fast', action='store_true', help='Fast mode (20 workers, ~1 hour)')
    parser.add_argument('--eco', action='store_true', help='Eco mode (4 workers, slow but safe)')
    parser.add_argument('--status', action='store_true', help='Show status only')
    parser.add_argument('--kill', action='store_true', help='Kill all processes first')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    
    args = parser.parse_args()
    
    # Determine mode
    if args.status:
        show_status()
        return
    
    mode = 'eco'
    if args.turbo:
        mode = 'turbo'
    elif args.fast:
        mode = 'fast'
    elif args.eco:
        mode = 'eco'
    
    mode_config = MODES[mode]
    
    print("=" * 60)
    print(f"BACKFILL MODE: {mode.upper()}")
    print("=" * 60)
    print()
    
    # Kill all if turbo mode or --kill flag
    if mode_config['kill'] or args.kill:
        print("WARNING: This will KILL all running trading systems!")
        print()
        if not args.yes:
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted")
                return
        print()
        kill_all()
        clean_temp_files()
    
    # Set environment
    set_env(mode_config)
    
    # Run backfill
    run_backfill()

if __name__ == "__main__":
    main()
