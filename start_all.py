#!/usr/bin/env python3
"""
================================================================================
UNIFIED TRADING SYSTEM LAUNCHER - V2
================================================================================
PURPOSE: Kill all existing processes, then start both Shoonya and Crypto together

FEATURES:
1. Aggressive cleanup - kills all processes on ports 8787, 8788
2. Kills all Python/Node processes related to trading apps
3. Starts both systems fresh on fixed ports
4. Parallel startup for faster initialization

PORTS (FIXED):
- Shoonya: 8787 (NSE/BSE/MCX)
- Crypto: 8788 (Delta India)

USAGE:
    python start_all.py

No arguments needed - just run and it handles everything:
    1. Kill all existing processes
    2. Start Shoonya on port 8787
    3. Start Crypto on port 8788
    4. Show status

GIT TRACKING:
    - Created: 2026-02-13
    - Modified: 2026-02-13 (aggressive cleanup + parallel start)
================================================================================
"""

import os
import sys
import time
import json
import subprocess
import signal
import socket
from pathlib import Path
from datetime import datetime
import threading
import urllib.request

# =============================================================================
# CONFIGURATION
# =============================================================================

ROOT = Path(__file__).parent.resolve()
CRYPTO_ROOT = ROOT / "crypto_app"

SHOONYA_PORT = 8787
CRYPTO_PORT = 8788

SHOONYA_URL = f"http://127.0.0.1:{SHOONYA_PORT}/"
CRYPTO_URL = f"http://127.0.0.1:{CRYPTO_PORT}/"
SHOONYA_HEALTH = f"http://127.0.0.1:{SHOONYA_PORT}/api/health"
CRYPTO_HEALTH = f"http://127.0.0.1:{CRYPTO_PORT}/api/health"

# Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(msg, color=Colors.ENDC):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{Colors.ENDC}")

def log_step(step, msg):
    log(f"[{step}/5] {msg}", Colors.BOLD)

def log_ok(msg):
    log(f"  [OK] {msg}", Colors.GREEN)

def log_warn(msg):
    log(f"  [WARN] {msg}", Colors.YELLOW)

def log_err(msg):
    log(f"  [ERR] {msg}", Colors.RED)

def log_info(msg):
    log(f"  [INFO] {msg}", Colors.BLUE)

# =============================================================================
# STEP 1: AGGRESSIVE CLEANUP
# =============================================================================

def is_port_in_use(port):
    """Check if port is in use"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def kill_port_processes(port):
    """Kill all processes using a specific port"""
    killed = []
    try:
        # Use netstat to find PIDs
        result = subprocess.run(
            ['netstat', '-ano', '|', 'findstr', f':{port}'],
            capture_output=True,
            text=True,
            shell=True
        )
        
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    try:
                        subprocess.run(['taskkill', '/F', '/PID', pid], 
                                     capture_output=True)
                        killed.append(pid)
                    except:
                        pass
    except Exception as e:
        log_warn(f"Could not kill port {port}: {e}")
    
    return killed

def kill_python_processes():
    """Kill all Python processes running trading apps"""
    killed = []
    try:
        # Find Python processes
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )
        
        for line in result.stdout.split('\n')[1:]:  # Skip header
            if 'python' in line.lower():
                parts = line.split('","')
                if len(parts) >= 2:
                    pid = parts[1].replace('"', '')
                    try:
                        # Check if it's our trading app by looking at command line
                        cmd_result = subprocess.run(
                            ['wmic', 'process', 'where', f'processid={pid}', 
                             'get', 'commandline', '/format:csv'],
                            capture_output=True,
                            text=True
                        )
                        cmd_line = cmd_result.stdout.lower()
                        
                        # Kill if it's our app
                        if any(x in cmd_line for x in ['historyapp', 'cryptoapp', 
                                                       'server.js', 'node_ui']):
                            subprocess.run(['taskkill', '/F', '/PID', pid],
                                         capture_output=True)
                            killed.append(pid)
                    except:
                        pass
    except Exception as e:
        log_warn(f"Could not kill Python processes: {e}")
    
    return killed

def kill_node_processes():
    """Kill all Node processes running UI servers"""
    killed = []
    try:
        # Find Node processes
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq node.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )
        
        for line in result.stdout.split('\n')[1:]:
            if 'node' in line.lower():
                parts = line.split('","')
                if len(parts) >= 2:
                    pid = parts[1].replace('"', '')
                    try:
                        # Check command line
                        cmd_result = subprocess.run(
                            ['wmic', 'process', 'where', f'processid={pid}',
                             'get', 'commandline', '/format:csv'],
                            capture_output=True,
                            text=True
                        )
                        cmd_line = cmd_result.stdout.lower()
                        
                        if 'server.js' in cmd_line or 'crypto_ui' in cmd_line:
                            subprocess.run(['taskkill', '/F', '/PID', pid],
                                         capture_output=True)
                            killed.append(pid)
                    except:
                        pass
    except Exception as e:
        log_warn(f"Could not kill Node processes: {e}")
    
    return killed

def aggressive_cleanup():
    """Kill all existing processes aggressively"""
    log_step(1, "CLEANUP: Killing all existing processes...")
    
    # Kill ports
    killed_8787 = kill_port_processes(SHOONYA_PORT)
    if killed_8787:
        log_ok(f"Killed {len(killed_8787)} process(es) on port {SHOONYA_PORT}")
    
    killed_8788 = kill_port_processes(CRYPTO_PORT)
    if killed_8788:
        log_ok(f"Killed {len(killed_8788)} process(es) on port {CRYPTO_PORT}")
    
    # Kill Python processes
    py_killed = kill_python_processes()
    if py_killed:
        log_ok(f"Killed {len(py_killed)} Python trading process(es)")
    
    # Kill Node processes
    node_killed = kill_node_processes()
    if node_killed:
        log_ok(f"Killed {len(node_killed)} Node UI process(es)")
    
    # Verify ports are free
    time.sleep(1)
    if is_port_in_use(SHOONYA_PORT):
        log_warn(f"Port {SHOONYA_PORT} still in use, forcing...")
        subprocess.run(['cmd', '/c', f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{SHOONYA_PORT}\') do taskkill /F /PID %a'], 
                      capture_output=True, shell=True)
    
    if is_port_in_use(CRYPTO_PORT):
        log_warn(f"Port {CRYPTO_PORT} still in use, forcing...")
        subprocess.run(['cmd', '/c', f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{CRYPTO_PORT}\') do taskkill /F /PID %a'],
                      capture_output=True, shell=True)
    
    time.sleep(1)
    
    # Final check
    shoonya_free = not is_port_in_use(SHOONYA_PORT)
    crypto_free = not is_port_in_use(CRYPTO_PORT)
    
    if shoonya_free and crypto_free:
        log_ok("All ports are free")
        return True
    else:
        if not shoonya_free:
            log_err(f"Port {SHOONYA_PORT} still in use!")
        if not crypto_free:
            log_err(f"Port {CRYPTO_PORT} still in use!")
        return False

# =============================================================================
# STEP 2: START SHOONYA
# =============================================================================

def start_shoonya():
    """Start Shoonya system on port 8787"""
    log_step(2, "STARTING: Shoonya (NSE/BSE/MCX) on port 8787...")
    
    # Check port is free
    if is_port_in_use(SHOONYA_PORT):
        log_err(f"Port {SHOONYA_PORT} is still in use!")
        return False
    
    # Start backend
    log_info("Starting Shoonya backend (historyapp.py)...")
    backend_cmd = f'"{sys.executable}" "{ROOT / "historyapp.py"}"'
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    
    log_info(f"Backend PID: {backend_proc.pid}")
    time.sleep(2)
    
    # Start UI
    log_info("Starting Shoonya UI (server.js) on port 8787...")
    ui_cmd = f'"{"node"}" "{ROOT / "node_ui" / "server.js"}"'
    ui_proc = subprocess.Popen(
        ui_cmd,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    
    log_info(f"UI PID: {ui_proc.pid}")
    time.sleep(3)
    
    # Wait for health check
    for i in range(10):
        if is_port_in_use(SHOONYA_PORT):
            try:
                urllib.request.urlopen(SHOONYA_HEALTH, timeout=2)
                log_ok("Shoonya is running and healthy")
                return True
            except:
                pass
        time.sleep(1)
    
    if is_port_in_use(SHOONYA_PORT):
        log_warn("Shoonya port is open but health check failed")
        return True
    else:
        log_err("Shoonya failed to start")
        return False

# =============================================================================
# STEP 3: START CRYPTO
# =============================================================================

def start_crypto():
    """Start Crypto system on port 8788"""
    log_step(3, "STARTING: Crypto (Delta India) on port 8788...")
    
    # Check port is free
    if is_port_in_use(CRYPTO_PORT):
        log_err(f"Port {CRYPTO_PORT} is still in use!")
        return False
    
    # Check credentials exist
    cred_file = CRYPTO_ROOT / "delta_cred.json"
    if not cred_file.exists():
        log_warn("delta_cred.json not found - Crypto will run in simulation mode")
    
    # Start backend
    log_info("Starting Crypto backend (cryptoapp.py)...")
    backend_cmd = f'"{sys.executable}" "{CRYPTO_ROOT / "cryptoapp.py"}"'
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(CRYPTO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    
    log_info(f"Backend PID: {backend_proc.pid}")
    time.sleep(2)
    
    # Start UI
    log_info("Starting Crypto UI (server.js) on port 8788...")
    env = os.environ.copy()
    env['CRYPTO_UI_PORT'] = str(CRYPTO_PORT)
    
    ui_cmd = f'"{"node"}" "{CRYPTO_ROOT / "crypto_ui" / "server.js"}"'
    ui_proc = subprocess.Popen(
        ui_cmd,
        cwd=str(CRYPTO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    
    log_info(f"UI PID: {ui_proc.pid}")
    time.sleep(3)
    
    # Wait for health check
    for i in range(10):
        if is_port_in_use(CRYPTO_PORT):
            try:
                urllib.request.urlopen(CRYPTO_HEALTH, timeout=2)
                log_ok("Crypto is running and healthy")
                return True
            except:
                pass
        time.sleep(1)
    
    if is_port_in_use(CRYPTO_PORT):
        log_warn("Crypto port is open but health check failed")
        return True
    else:
        log_err("Crypto failed to start")
        return False

# =============================================================================
# STEP 4: VERIFY BOTH RUNNING
# =============================================================================

def verify_systems():
    """Verify both systems are running"""
    log_step(4, "VERIFYING: Both systems are running...")
    
    shoonya_ok = is_port_in_use(SHOONYA_PORT)
    crypto_ok = is_port_in_use(CRYPTO_PORT)
    
    if shoonya_ok:
        try:
            urllib.request.urlopen(SHOONYA_HEALTH, timeout=2)
            log_ok(f"Shoonya: {SHOONYA_URL} [HEALTHY]")
        except:
            log_warn(f"Shoonya: {SHOONYA_URL} [PORT OPEN]")
    else:
        log_err(f"Shoonya: NOT RUNNING")
    
    if crypto_ok:
        try:
            urllib.request.urlopen(CRYPTO_HEALTH, timeout=2)
            log_ok(f"Crypto:  {CRYPTO_URL} [HEALTHY]")
        except:
            log_warn(f"Crypto:  {CRYPTO_URL} [PORT OPEN]")
    else:
        log_err(f"Crypto: NOT RUNNING")
    
    return shoonya_ok, crypto_ok

# =============================================================================
# STEP 5: PRINT STATUS
# =============================================================================

def print_final_status(shoonya_ok, crypto_ok):
    """Print final status"""
    log_step(5, "STATUS: Final system status")
    
    print(f"""
{Colors.BOLD}================================================================
                    SYSTEM STATUS
================================================================{Colors.ENDC}

{Colors.BLUE}SHOONYA (NSE/BSE/MCX){Colors.ENDC}
  Status: {Colors.GREEN if shoonya_ok else Colors.RED}{'RUNNING' if shoonya_ok else 'DOWN'}{Colors.ENDC}
  Port: {SHOONYA_PORT}
  URL: {SHOONYA_URL}
  Market: 9:15 AM IST

{Colors.CYAN}CRYPTO (Delta India){Colors.ENDC}
  Status: {Colors.GREEN if crypto_ok else Colors.RED}{'RUNNING' if crypto_ok else 'DOWN'}{Colors.ENDC}
  Port: {CRYPTO_PORT}
  URL: {CRYPTO_URL}
  Market: 00:00 UTC (5:30 AM IST)

{Colors.BOLD}================================================================
{Colors.GREEN if (shoonya_ok and crypto_ok) else Colors.YELLOW}  {'ALL SYSTEMS OPERATIONAL' if (shoonya_ok and crypto_ok) else 'SOME SYSTEMS FAILED'}{Colors.ENDC}
{Colors.BOLD}================================================================{Colors.ENDC}
""")
    
    if shoonya_ok and crypto_ok:
        log("Access your dashboards:", Colors.GREEN)
        log(f"  Shoonya: {SHOONYA_URL}", Colors.BLUE)
        log(f"  Crypto:  {CRYPTO_URL}", Colors.CYAN)

# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point - no arguments needed"""
    print(f"""
{Colors.BOLD}{Colors.HEADER}
================================================================
        UNIFIED TRADING SYSTEM LAUNCHER
        Shoonya + Crypto | Fixed Ports | Auto-Cleanup
================================================================{Colors.ENDC}
""")
    
    log("Starting unified trading systems...", Colors.BOLD)
    print()
    
    # Step 1: Aggressive cleanup
    if not aggressive_cleanup():
        log_err("Cleanup failed - ports still in use")
        print_final_status(False, False)
        return 1
    
    print()
    
    # Step 2 & 3: Start both systems (can be parallel)
    shoonya_thread = threading.Thread(target=start_shoonya)
    crypto_thread = threading.Thread(target=start_crypto)
    
    shoonya_thread.start()
    time.sleep(1)  # Slight delay to avoid resource conflict
    crypto_thread.start()
    
    shoonya_thread.join()
    crypto_thread.join()
    
    print()
    
    # Step 4: Verify
    shoonya_ok, crypto_ok = verify_systems()
    
    print()
    
    # Step 5: Print status
    print_final_status(shoonya_ok, crypto_ok)
    
    return 0 if (shoonya_ok and crypto_ok) else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}")
        sys.exit(1)
