import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = ROOT / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
STATE_FILE = RUNTIME_DIR / "state.json"

BACKEND_LOG = LOG_DIR / "historyapp.log"
UI_LOG = LOG_DIR / "node_ui.log"
UI_URL = "http://127.0.0.1:8787/"
HEALTH_URL = "http://127.0.0.1:8787/api/health"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

BACKEND_PATTERN = r"historyapp\.py"
UI_PATTERN = r"node_ui\\server\.js"

LEGACY_PATHS = [
    ROOT / "history_dashboard.py",
    ROOT / "benchmark_api.py",
    ROOT / "api_helper.py",
    ROOT / "shoonya_login.py",
    ROOT / "shoonya_ui.py",
    ROOT / "superalgo_multi.py",
    ROOT / "history_out" / "bench_ticks.csv",
    ROOT / "history_out" / "first_closes.json",
    ROOT / "__pycache__",
]


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{ts()}] {msg}")


def ensure_dirs():
    RUNTIME_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    (ROOT / "history_out").mkdir(exist_ok=True)


def read_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(data):
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_ps(script):
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
    )


def pids_by_pattern(pattern):
    script = (
        "$p=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '"
        + pattern
        + "' } | Select-Object -ExpandProperty ProcessId; "
        "if ($p) { $p | ConvertTo-Json -Compress }"
    )
    r = run_ps(script)
    if r.returncode != 0:
        return []
    out = (r.stdout or "").strip()
    if not out:
        return []
    try:
        data = json.loads(out)
        if isinstance(data, int):
            return [data]
        if isinstance(data, list):
            return [int(x) for x in data]
    except Exception:
        pass
    return []


def is_pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def kill_pid(pid):
    if not pid:
        return
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)


def kill_by_pattern(pattern):
    pids = pids_by_pattern(pattern)
    for pid in pids:
        kill_pid(pid)
    return pids


def ui_health(timeout=3):
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def remove_path(p: Path):
    if not p.exists():
        return False
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    else:
        p.unlink(missing_ok=True)
    return True


def cleanup_legacy():
    removed = []
    for p in LEGACY_PATHS:
        try:
            if remove_path(p):
                removed.append(str(p))
        except Exception:
            pass
    return removed


def start_proc(cmd, log_file):
    with open(log_file, "a", encoding="utf-8") as lf:
        p = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=lf,
            stderr=subprocess.STDOUT,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    return p.pid


def do_stop():
    state = read_state()

    for pid in [state.get("backend_pid"), state.get("ui_pid")]:
        if pid and is_pid_alive(pid):
            kill_pid(pid)

    extra_backend = kill_by_pattern(BACKEND_PATTERN)
    extra_ui = kill_by_pattern(UI_PATTERN)

    if STATE_FILE.exists():
        STATE_FILE.unlink(missing_ok=True)

    log(f"Stopped. backend_matches={len(extra_backend)} ui_matches={len(extra_ui)}")


def do_start(clean=False):
    ensure_dirs()

    if clean:
        removed = cleanup_legacy()
        if removed:
            log("Removed legacy files:")
            for x in removed:
                log(f"  - {x}")

    do_stop()
    time.sleep(1)

    if not (ROOT / "historyapp.py").exists():
        raise SystemExit("historyapp.py not found")
    if not (ROOT / "node_ui" / "server.js").exists():
        raise SystemExit("node_ui/server.js not found")

    backend_pid = start_proc([sys.executable, "-u", "historyapp.py"], BACKEND_LOG)
    ui_pid = start_proc(["node", str(ROOT / "node_ui" / "server.js")], UI_LOG)

    state = {
        "started_at": ts(),
        "backend_pid": backend_pid,
        "ui_pid": ui_pid,
        "backend_log": str(BACKEND_LOG),
        "ui_log": str(UI_LOG),
    }
    write_state(state)

    time.sleep(2)
    log(f"Started backend pid={backend_pid} alive={is_pid_alive(backend_pid)}")
    log(f"Started node_ui pid={ui_pid} alive={is_pid_alive(ui_pid)} health={ui_health(timeout=2)}")
    log(f"UI: {UI_URL}")


def do_status():
    state = read_state()
    backend_pid = state.get("backend_pid")
    ui_pid = state.get("ui_pid")

    log(f"State file: {'present' if state else 'missing'}")
    log(f"backend_pid={backend_pid} alive={is_pid_alive(backend_pid)} matches={pids_by_pattern(BACKEND_PATTERN)}")
    log(f"ui_pid={ui_pid} alive={is_pid_alive(ui_pid)} matches={pids_by_pattern(UI_PATTERN)}")
    log(f"ui_health={ui_health(timeout=2)} url={UI_URL}")


def do_clean():
    removed = cleanup_legacy()
    if removed:
        log("Removed:")
        for x in removed:
            log(f"  - {x}")
    else:
        log("No legacy files found.")


def main():
    ap = argparse.ArgumentParser(description="History app process manager")
    ap.add_argument("command", nargs="?", default="start", choices=["start", "stop", "restart", "status", "clean"], help="default: start")
    ap.add_argument("--clean", action="store_true", help="cleanup legacy files during start/restart")
    args = ap.parse_args()

    if args.command == "start":
        do_start(clean=args.clean)
    elif args.command == "stop":
        do_stop()
    elif args.command == "restart":
        do_stop()
        time.sleep(1)
        do_start(clean=args.clean)
    elif args.command == "status":
        do_status()
    elif args.command == "clean":
        do_clean()


if __name__ == "__main__":
    main()

