#!/usr/bin/env python3
"""
================================================================================
CRYPTO APP STARTER - Delta India Exchange Manager
================================================================================
REPLICATED FROM: app_start.py (Shoonya Version)
PURPOSE: Manage crypto trading app lifecycle (start/stop/status/restart)

GIT TRACKING:
- Created: 2026-02-13
- Author: AI Assistant
- Feature: Initial crypto app starter script
- Status: New file - no modifications to existing codebase

This script manages:
1. cryptoapp.py (backend - Delta India API client)
2. crypto_ui/server.js (frontend - Dashboard on port 8788)

PORTS:
- Backend: No external port (internal WebSocket + REST to Delta)
- UI: 8788 (different from Shoonya's 8787)
================================================================================
"""

import os
import sys
import json
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

ROOT = Path(__file__).parent.resolve()
RUNTIME_DIR = ROOT / "runtime"
LOG_DIR = ROOT / "logs"

# Ensure directories exist
for d in [RUNTIME_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

STATE_FILE = RUNTIME_DIR / "crypto_state.json"
BACKEND_LOG = LOG_DIR / "cryptoapp.log"
UI_LOG = LOG_DIR / "crypto_ui.log"

UI_PORT = 8788  # Different from Shoonya's 8787
UI_URL = f"http://127.0.0.1:{UI_PORT}/"

# Process identification patterns
BACKEND_PATTERN = r"cryptoapp\.py"
UI_PATTERN = r"crypto_ui[\\/]server\.js"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log(msg: str):
    """Print with timestamp"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def load_state() -> dict:
    """Load process state from file"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'backend_pid': None, 'ui_pid': None}

def save_state(state: dict):
    """Save process state to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def is_pid_alive(pid: int) -> bool:
    """Check if a process is running"""
    if not pid:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        # Fallback for Windows without psutil
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(1, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False

def kill_process(pid: int) -> bool:
    """Kill a process by PID"""
    if not pid:
        return False
    try:
        import psutil
        process = psutil.Process(pid)
        process.terminate()
        process.wait(timeout=5)
        return True
    except:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
                return True
        except:
            pass
    return False

def find_processes(pattern: str) -> list:
    """Find PIDs matching a pattern"""
    pids = []
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if pattern in cmdline:
                    pids.append(proc.info['pid'])
            except:
                pass
    except ImportError:
        # Fallback using wmic
        import subprocess
        try:
            result = subprocess.run(['wmic', 'process', 'get', 'processid,commandline'], 
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if pattern in line:
                    parts = line.strip().split()
                    if parts:
                        try:
                            pids.append(int(parts[-1]))
                        except:
                            pass
        except:
            pass
    return pids

def kill_port_listeners(port: int) -> list:
    """Kill processes listening on a port"""
    killed = []
    try:
        import psutil
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                try:
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed.append(conn.pid)
                except:
                    pass
    except:
        pass
    return killed

def start_backend() -> int:
    """Start the crypto backend (cryptoapp.py)"""
    log("Starting crypto backend...")
    
    cmd = [sys.executable, "-u", str(ROOT / "cryptoapp.py")]
    
    # Open log file
    with open(BACKEND_LOG, 'a') as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
    
    log(f"Backend started with PID {proc.pid}")
    return proc.pid

def start_ui() -> int:
    """Start the crypto UI server"""
    log("Starting crypto UI...")
    
    cmd = ["node", str(ROOT / "crypto_ui" / "server.js")]
    
    # Set environment variable for port
    env = os.environ.copy()
    env['CRYPTO_UI_PORT'] = str(UI_PORT)
    
    with open(UI_LOG, 'a') as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
    
    log(f"UI started with PID {proc.pid}")
    return proc.pid

def check_ui_health(timeout: int = 5) -> bool:
    """Check if UI is responding"""
    try:
        import urllib.request
        import ssl
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(f"{UI_URL}api/health", method='GET')
        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return response.status == 200
    except:
        return False

# =============================================================================
# COMMAND HANDLERS
# =============================================================================

def cmd_start():
    """Start the crypto app"""
    log("=" * 60)
    log("CRYPTO APP STARTER - Delta India Exchange")
    log("=" * 60)
    
    # Check credentials exist
    cred_file = ROOT / "delta_cred.json"
    if not cred_file.exists():
        log(f"ERROR: Credentials file not found: {cred_file}")
        log("Please create delta_cred.json with your API credentials")
        return 1
    
    # Load existing state
    state = load_state()
    
    # Check if already running
    backend_alive = is_pid_alive(state.get('backend_pid'))
    ui_alive = is_pid_alive(state.get('ui_pid'))
    
    if backend_alive and ui_alive:
        log("Crypto app is already running!")
        log(f"UI: {UI_URL}")
        return 0
    
    # Kill any lingering processes
    log("Cleaning up any existing processes...")
    kill_port_listeners(UI_PORT)
    
    # Kill old PIDs if they exist
    if state.get('backend_pid'):
        kill_process(state['backend_pid'])
    if state.get('ui_pid'):
        kill_process(state['ui_pid'])
    
    # Start backend
    backend_pid = start_backend()
    time.sleep(2)  # Give backend time to initialize
    
    # Start UI
    ui_pid = start_ui()
    time.sleep(3)  # Give UI time to start
    
    # Check health
    ui_healthy = check_ui_health()
    backend_healthy = is_pid_alive(backend_pid)
    
    # Save state
    save_state({
        'backend_pid': backend_pid,
        'ui_pid': ui_pid,
        'started_at': datetime.now().isoformat(),
        'ui_url': UI_URL
    })
    
    log("-" * 60)
    log(f"Backend PID: {backend_pid} | Alive: {backend_healthy}")
    log(f"UI PID: {ui_pid} | Alive: {ui_alive} | Health: {ui_healthy}")
    log(f"UI URL: {UI_URL}")
    log("=" * 60)
    
    if ui_healthy and backend_healthy:
        log("✅ Crypto app started successfully!")
        return 0
    else:
        log("⚠️  App started but health check failed")
        return 1

def cmd_stop():
    """Stop the crypto app"""
    log("Stopping crypto app...")
    
    state = load_state()
    
    # Kill processes
    backend_killed = kill_process(state.get('backend_pid'))
    ui_killed = kill_process(state.get('ui_pid'))
    
    # Kill any stragglers
    backend_pids = find_processes(BACKEND_PATTERN)
    ui_pids = find_processes(UI_PATTERN)
    
    for pid in backend_pids:
        if pid != state.get('backend_pid'):
            kill_process(pid)
    
    for pid in ui_pids:
        if pid != state.get('ui_pid'):
            kill_process(pid)
    
    # Kill port listeners
    port_killed = kill_port_listeners(UI_PORT)
    
    # Clear state
    save_state({'backend_pid': None, 'ui_pid': None})
    
    log(f"Stopped. Backend killed: {backend_killed} | UI killed: {ui_killed} | Port cleanup: {len(port_killed)}")
    return 0

def cmd_status():
    """Check status of crypto app"""
    log("Checking crypto app status...")
    
    state = load_state()
    backend_alive = is_pid_alive(state.get('backend_pid'))
    ui_alive = is_pid_alive(state.get('ui_pid'))
    ui_healthy = check_ui_health() if ui_alive else False
    
    log(f"State file: {'present' if state.get('backend_pid') else 'empty'}")
    log(f"Backend PID: {state.get('backend_pid')} | Alive: {backend_alive}")
    log(f"UI PID: {state.get('ui_pid')} | Alive: {ui_alive} | Health: {ui_healthy}")
    log(f"UI URL: {UI_URL}")
    
    if backend_alive and ui_healthy:
        log("✅ Crypto app is running normally")
        return 0
    elif backend_alive or ui_alive:
        log("⚠️  Partial failure - some components not responding")
        return 1
    else:
        log("❌ Crypto app is not running")
        return 1

def cmd_restart():
    """Restart the crypto app"""
    log("Restarting crypto app...")
    cmd_stop()
    time.sleep(2)
    return cmd_start()

def cmd_logs():
    """Show recent logs"""
    log("Recent backend logs:")
    log("-" * 40)
    try:
        with open(BACKEND_LOG, 'r') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    except:
        log("No backend logs available")
    
    log("\nRecent UI logs:")
    log("-" * 40)
    try:
        with open(UI_LOG, 'r') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    except:
        log("No UI logs available")

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python app_start.py [start|stop|restart|status|logs]")
        return 1
    
    command = sys.argv[1].lower()
    
    commands = {
        'start': cmd_start,
        'stop': cmd_stop,
        'restart': cmd_restart,
        'status': cmd_status,
        'logs': cmd_logs,
    }
    
    if command in commands:
        return commands[command]()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: start, stop, restart, status, logs")
        return 1

if __name__ == "__main__":
    sys.exit(main())
