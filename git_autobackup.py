import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(cmd):
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)


def has_changes():
    r = run(["git", "status", "--porcelain"])
    return r.returncode == 0 and bool((r.stdout or "").strip())


def backup_once():
    if not has_changes():
        return False

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"auto-backup {ts}"

    run(["git", "add", "-A"])
    c = run(["git", "commit", "-m", msg])
    if c.returncode != 0:
        return False
    run(["git", "push"])
    return True


def main():
    ap = argparse.ArgumentParser(description="Auto git backup loop")
    ap.add_argument("--interval-min", type=int, default=10, help="backup interval in minutes")
    ap.add_argument("--once", action="store_true", help="run one backup cycle and exit")
    args = ap.parse_args()

    if args.once:
        changed = backup_once()
        print("backup_done" if changed else "no_changes")
        return

    sleep_sec = max(60, args.interval_min * 60)
    while True:
        try:
            backup_once()
        except Exception:
            pass
        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
