#!/usr/bin/env python3
"""
================================================================================
UNIFIED TRADING SYSTEM LAUNCHER
================================================================================
PURPOSE: Start both Shoonya (NSE/BSE/MCX) and Crypto (Delta India) apps together

USAGE:
    python start_all.py start    # Start both systems
    python start_all.py stop     # Stop both systems
    python start_all.py restart  # Restart both systems
    python start_all.py status   # Check status of both
    python start_all.py logs     # Show logs from both

PORTS:
    Shoonya: http://127.0.0.1:8787 (NSE/BSE/MCX)
    Crypto:  http://127.0.0.1:8788 (Delta India)

GIT TRACKING:
    - Created: 2026-02-13
    - Author: AI Assistant
    - Feature: Unified launcher for both trading systems
================================================================================
"""

import os
import sys
import time
import json
import subprocess
import signal
from pathlib import Path
from datetime import datetime
import threading
import urllib.request

# Configuration
ROOT = Path(__file__).parent.resolve()
CRYPTO_ROOT = ROOT / "crypto_app"

SHOONYA_UI_URL = "http://127.0.0.1:8787/"
CRYPTO_UI_URL = "http://127.0.0.1:8788/"
SHOONYA_HEALTH = "http://127.0.0.1:8787/api/health"
CRYPTO_HEALTH = "http://127.0.0.1:8788/api/health"

STATE_FILE = ROOT / "runtime" / "unified_state.json"

# ANSI Colors for terminal output
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
    """Print with timestamp and color"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}[{ts}] {msg}{Colors.ENDC}")

def log_shoonya(msg):
    """Log for Shoonya system"""
    log(f"[SHOONYA] {msg}", Colors.BLUE)

def log_crypto(msg):
    """Log for Crypto system"""
    log(f"[CRYPTO] {msg}", Colors.CYAN)

def log_success(msg):
    log("[OK] " + msg, Colors.GREEN)

def log_warning(msg):
    log("[WARN] " + msg, Colors.YELLOW)

def log_error(msg):
    log("[ERROR] " + msg, Colors.RED)

def load_state():
    """Load unified state"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log_error(f"Error loading state: {e}")
    return {'shoonya': {}, 'crypto': {}}

def save_state(state):
    """Save unified state"""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log_error(f"Error saving state: {e}")

def is_port_open(port, timeout=2):
    """Check if port is responding"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def check_health(url, timeout=3):
    """Check health endpoint"""
    try:
        req = urllib.request.Request(url, method='GET')
        response = urllib.request.urlopen(req, timeout=timeout)
        return response.status == 200
    except:
        return False

def run_command(cmd, cwd=None, wait=True):
    """Run a command and return result"""
    try:
        if wait:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                shell=True
            )
            return result.returncode == 0, result.stdout, result.stderr
        else:
            # Don't wait - background process
            subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            return True, "", ""
    except Exception as e:
        return False, "", str(e)

def print_banner():
    """Print unified launcher banner"""
    print(f"""
{Colors.BOLD}{Colors.HEADER}
====================================================================
             UNIFIED TRADING SYSTEM LAUNCHER
====================================================================
  Shoonya (NSE/BSE/MCX)  ->  http://127.0.0.1:8787/
  Crypto (Delta India)   ->  http://127.0.0.1:8788/
====================================================================
{Colors.ENDC}
""")

def start_shoonya():
    """Start Shoonya system"""
    log_shoonya("Starting Shoonya trading system...")
    
    # Check if already running
    if is_port_open(8787):
        log_warning("Shoonya port 8787 already open")
        return True
    
    # Run app_start.py for shoonya
    cmd = f'"{sys.executable}" "{ROOT / "app_start.py"}" start'
    success, stdout, stderr = run_command(cmd, cwd=ROOT)
    
    if success:
        log_shoonya("Start command executed")
        time.sleep(3)  # Wait for startup
        
        if check_health(SHOONYA_HEALTH):
            log_success("Shoonya is running")
            return True
        else:
            log_error("Shoonya health check failed")
            return False
    else:
        log_error(f"Failed to start Shoonya: {stderr}")
        return False

def start_crypto():
    """Start Crypto system"""
    log_crypto("Starting Crypto trading system...")
    
    # Check if already running
    if is_port_open(8788):
        log_warning("Crypto port 8788 already open")
        return True
    
    # Check credentials exist
    cred_file = CRYPTO_ROOT / "delta_cred.json"
    if not cred_file.exists():
        log_error(f"Crypto credentials not found: {cred_file}")
        log_crypto("Please create delta_cred.json with your API credentials")
        return False
    
    # Run app_start.py for crypto
    cmd = f'"{sys.executable}" "{CRYPTO_ROOT / "app_start.py"}" start'
    success, stdout, stderr = run_command(cmd, cwd=CRYPTO_ROOT)
    
    if success:
        log_crypto("Start command executed")
        time.sleep(3)  # Wait for startup
        
        if check_health(CRYPTO_HEALTH):
            log_success("Crypto is running")
            return True
        else:
            log_error("Crypto health check failed")
            return False
    else:
        log_error(f"Failed to start Crypto: {stderr}")
        return False

def stop_shoonya():
    """Stop Shoonya system"""
    log_shoonya("Stopping Shoonya...")
    cmd = f'"{sys.executable}" "{ROOT / "app_start.py"}" stop'
    run_command(cmd, cwd=ROOT)
    time.sleep(2)
    log_success("Shoonya stopped")

def stop_crypto():
    """Stop Crypto system"""
    log_crypto("Stopping Crypto...")
    cmd = f'"{sys.executable}" "{CRYPTO_ROOT / "app_start.py"}" stop'
    run_command(cmd, cwd=CRYPTO_ROOT)
    time.sleep(2)
    log_success("Crypto stopped")

def get_shoonya_status():
    """Get detailed Shoonya status"""
    port_open = is_port_open(8787)
    healthy = check_health(SHOONYA_HEALTH) if port_open else False
    
    return {
        'name': 'Shoonya',
        'port': 8787,
        'port_open': port_open,
        'healthy': healthy,
        'url': SHOONYA_UI_URL,
        'markets': 'NSE/BSE/MCX',
        'time': '9:15 AM IST',
        'status': 'RUNNING' if healthy else 'DOWN'
    }

def get_crypto_status():
    """Get detailed Crypto status"""
    port_open = is_port_open(8788)
    healthy = check_health(CRYPTO_HEALTH) if port_open else False
    
    return {
        'name': 'Crypto',
        'port': 8788,
        'port_open': port_open,
        'healthy': healthy,
        'url': CRYPTO_UI_URL,
        'markets': 'Delta India',
        'time': '00:00 UTC (5:30 AM IST)',
        'status': 'RUNNING' if healthy else 'DOWN'
    }

def print_status():
    """Print status table"""
    shoonya = get_shoonya_status()
    crypto = get_crypto_status()
    
    print(f"""
{Colors.BOLD}SYSTEM STATUS{Colors.ENDC}
{'-' * 70}
{Colors.BLUE}Shoonya (NSE/BSE/MCX){Colors.ENDC}
  Port: {shoonya['port']} | Status: {Colors.GREEN if shoonya['healthy'] else Colors.RED}{shoonya['status']}{Colors.ENDC}
  URL: {shoonya['url']}
  Market Open: {shoonya['time']}

{Colors.CYAN}Crypto (Delta India){Colors.ENDC}
  Port: {crypto['port']} | Status: {Colors.GREEN if crypto['healthy'] else Colors.RED}{crypto['status']}{Colors.ENDC}
  URL: {crypto['url']}
  Market Open: {crypto['time']}
{'-' * 70}
""")
    
    return shoonya['healthy'], crypto['healthy']

def show_logs(lines=20):
    """Show recent logs from both systems"""
    print(f"\n{Colors.BOLD}RECENT LOGS{Colors.ENDC}\n")
    
    # Shoonya logs
    shoonya_log = ROOT / "runtime" / "logs" / "historyapp.log"
    print(f"{Colors.BLUE}=== Shoonya Backend ==={Colors.ENDC}")
    if shoonya_log.exists():
        try:
            with open(shoonya_log, 'r') as f:
                log_lines = f.readlines()[-lines:]
                for line in log_lines:
                    print(line.rstrip())
        except Exception as e:
            print(f"Error reading log: {e}")
    else:
        print("Log file not found")
    
    print()
    
    # Crypto logs
    crypto_log = CRYPTO_ROOT / "logs" / "cryptoapp.log"
    print(f"{Colors.CYAN}=== Crypto Backend ==={Colors.ENDC}")
    if crypto_log.exists():
        try:
            with open(crypto_log, 'r') as f:
                log_lines = f.readlines()[-lines:]
                for line in log_lines:
                    print(line.rstrip())
        except Exception as e:
            print(f"Error reading log: {e}")
    else:
        print("Log file not found")

def cmd_start():
    """Start both systems"""
    print_banner()
    log("Starting unified trading systems...", Colors.BOLD)
    print()
    
    # Start Shoonya
    shoonya_ok = start_shoonya()
    print()
    
    # Start Crypto
    crypto_ok = start_crypto()
    print()
    
    # Final status
    log("-" * 70, Colors.BOLD)
    if shoonya_ok and crypto_ok:
        log_success("ALL SYSTEMS RUNNING")
        log(f"Shoonya: {SHOONYA_UI_URL}", Colors.BLUE)
        log(f"Crypto:  {CRYPTO_UI_URL}", Colors.CYAN)
    elif shoonya_ok:
        log_warning("Shoonya running, Crypto failed")
    elif crypto_ok:
        log_warning("Crypto running, Shoonya failed")
    else:
        log_error("BOTH SYSTEMS FAILED")
    log("-" * 70, Colors.BOLD)
    
    # Save state
    save_state({
        'shoonya': {'running': shoonya_ok, 'started_at': datetime.now().isoformat()},
        'crypto': {'running': crypto_ok, 'started_at': datetime.now().isoformat()},
        'started_at': datetime.now().isoformat()
    })
    
    return 0 if (shoonya_ok or crypto_ok) else 1

def cmd_stop():
    """Stop both systems"""
    print_banner()
    log("Stopping unified trading systems...", Colors.BOLD)
    print()
    
    stop_shoonya()
    print()
    stop_crypto()
    print()
    
    log_success("All systems stopped")
    
    # Clear state
    save_state({'shoonya': {}, 'crypto': {}})
    
    return 0

def cmd_restart():
    """Restart both systems"""
    cmd_stop()
    print("\n" + "=" * 70 + "\n")
    time.sleep(2)
    return cmd_start()

def cmd_status():
    """Show status of both systems"""
    print_banner()
    shoonya_ok, crypto_ok = print_status()
    
    if shoonya_ok and crypto_ok:
        return 0
    else:
        return 1

def cmd_logs():
    """Show logs"""
    print_banner()
    show_logs(30)
    return 0

def cmd_dashboard():
    """Open dashboards in browser"""
    print_banner()
    log("Opening dashboards...")
    
    try:
        import webbrowser
        
        shoonya = get_shoonya_status()
        crypto = get_crypto_status()
        
        if shoonya['healthy']:
            webbrowser.open(SHOONYA_UI_URL)
            log_shoonya("Dashboard opened in browser")
        
        if crypto['healthy']:
            webbrowser.open(CRYPTO_UI_URL)
            log_crypto("Dashboard opened in browser")
        
        if not shoonya['healthy'] and not crypto['healthy']:
            log_error("No systems running! Start with: python start_all.py start")
            return 1
            
    except Exception as e:
        log_error(f"Error opening browser: {e}")
        log(f"Shoonya: {SHOONYA_UI_URL}")
        log(f"Crypto:  {CRYPTO_UI_URL}")
    
    return 0

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(f"""
{Colors.BOLD}Unified Trading System Launcher{Colors.ENDC}

Usage:
    python start_all.py {Colors.GREEN}start{Colors.ENDC}      - Start both systems
    python start_all.py {Colors.RED}stop{Colors.ENDC}       - Stop both systems
    python start_all.py {Colors.YELLOW}restart{Colors.ENDC}   - Restart both systems
    python start_all.py {Colors.BLUE}status{Colors.ENDC}     - Check status
    python start_all.py {Colors.CYAN}logs{Colors.ENDC}       - Show recent logs
    python start_all.py {Colors.HEADER}dashboard{Colors.ENDC} - Open dashboards

Examples:
    python start_all.py start
    python start_all.py status
    python start_all.py logs
""")
        return 1
    
    command = sys.argv[1].lower()
    
    commands = {
        'start': cmd_start,
        'stop': cmd_stop,
        'restart': cmd_restart,
        'status': cmd_status,
        'logs': cmd_logs,
        'dashboard': cmd_dashboard,
    }
    
    if command in commands:
        try:
            return commands[command]()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}")
            return 1
    else:
        log_error(f"Unknown command: {command}")
        log(f"Use: start, stop, restart, status, logs, dashboard")
        return 1

if __name__ == "__main__":
    sys.exit(main())
