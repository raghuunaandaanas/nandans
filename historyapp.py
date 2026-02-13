import csv
import json
import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from threading import Lock, Thread

import pyotp
from NorenRestApiPy.NorenApi import NorenApi


ROOT = Path(__file__).resolve().parent
SYMBOL_DIR = ROOT / "symbols"
CRED_FILE = ROOT / "shoonya_cred.json"
DOWNLOAD_SCRIPT = ROOT / "download_symbols.py"
OUT_DIR = ROOT / "history_out"
OUT_DIR.mkdir(exist_ok=True)

SYMBOL_CACHE_FILE = OUT_DIR / "symbols_cache.json"
TICKS_FILE = OUT_DIR / "ticks.csv"
UI_SNAPSHOT_FILE = OUT_DIR / "ui_current_day.json"
DB_FILE = OUT_DIR / "first_closes.db"

FETCH_WORKERS = int(os.getenv("FIRST_CLOSE_WORKERS", "4"))
MAX_REST_SESSIONS = int(os.getenv("MAX_REST_SESSIONS", "4"))
MAX_FETCH_RETRIES = int(os.getenv("FIRST_CLOSE_MAX_RETRIES", "3"))
FETCH_SAVE_EVERY = int(os.getenv("FIRST_CLOSE_SAVE_EVERY", "300"))

CURRENT_DAY_BATCH = int(os.getenv("CURRENT_DAY_BATCH", "1200"))
CURRENT_DAY_SLEEP_SEC = float(os.getenv("CURRENT_DAY_SLEEP", "5"))

HISTORY_BATCH = int(os.getenv("HISTORY_BATCH", "1000"))
HISTORY_SLEEP_SEC = float(os.getenv("HISTORY_SLEEP", "5"))
HISTORY_MAX_LOOKBACK_DAYS = int(os.getenv("HISTORY_MAX_LOOKBACK_DAYS", "5000"))
HISTORY_STOP_EMPTY_STREAK = int(os.getenv("HISTORY_STOP_EMPTY_STREAK", "30"))

SUBSCRIBE_BATCH_SIZE = int(os.getenv("SUBSCRIBE_BATCH_SIZE", "1000"))
SUBSCRIBE_SLEEP_SEC = float(os.getenv("SUBSCRIBE_SLEEP_SEC", "0.2"))
MAX_SUBSCRIBE_SYMBOLS = int(os.getenv("MAX_SUBSCRIBE_SYMBOLS", "0"))

TICK_FLUSH_SIZE = int(os.getenv("TICK_FLUSH_SIZE", "500"))
TICK_FLUSH_INTERVAL_SEC = float(os.getenv("TICK_FLUSH_INTERVAL_SEC", "1.0"))
UI_SNAPSHOT_INTERVAL_SEC = float(os.getenv("UI_SNAPSHOT_INTERVAL_SEC", "3.0"))
UI_MAX_ROWS = int(os.getenv("UI_MAX_ROWS", "0"))
TODAY_DB_FLUSH_INTERVAL_SEC = float(os.getenv("TODAY_DB_FLUSH_INTERVAL_SEC", "5.0"))
TODAY_DB_FLUSH_MAX_ROWS = int(os.getenv("TODAY_DB_FLUSH_MAX_ROWS", "5000"))

MARKET_OPEN = {
    "NSE": dtime(9, 15),
    "NFO": dtime(9, 15),
    "BSE": dtime(9, 15),
    "BFO": dtime(9, 15),
    "MCX": dtime(9, 0),
}


lock = Lock()
api = None
rest_clients = []
db = None

symbol_map = {}
ordered_symbols = []
today_rows = {}
dirty_today = set()
pending_today = set()
today_fail_counts = {}
target_minutes = {}

ltp_map = {}
volume_map = {}
socket_opened = False

_tick_buffer = []
_ticks_received = 0
_ticks_flushed = 0
_last_tick_flush_ts = time.time()
_last_ui_snapshot_ts = 0.0
_ui_dirty = True


TODAY = date.today()
TODAY_S = TODAY.isoformat()
YESTERDAY_S = (TODAY - timedelta(days=1)).isoformat()


def log(msg):
    try:
        print(msg, flush=True)
    except OSError:
        pass


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def write_json_atomic(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(path)


def ensure_symbol_files():
    files = sorted(SYMBOL_DIR.glob("*.txt"))
    if files:
        return files
    log("No symbol txt files found. Running download_symbols.py ...")
    subprocess.check_call([sys.executable, str(DOWNLOAD_SCRIPT)], cwd=str(ROOT))
    return sorted(SYMBOL_DIR.glob("*.txt"))


def file_fingerprint(paths):
    fp = {}
    for p in paths:
        st = p.stat()
        fp[str(p)] = {"mtime_ns": st.st_mtime_ns, "size": st.st_size}
    return fp


def parse_symbols(paths):
    out = {}
    for p in paths:
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue
            exch, token = parts[0], parts[1]
            out[f"{exch}|{token}"] = {
                "exchange": exch,
                "token": token,
                "tsym": parts[4] if len(parts) > 4 and parts[4] else token,
            }
    return out


def load_symbols():
    paths = ensure_symbol_files()
    fp = file_fingerprint(paths)

    if SYMBOL_CACHE_FILE.exists():
        cache = json.loads(SYMBOL_CACHE_FILE.read_text(encoding="utf-8"))
        if cache.get("fingerprint") == fp:
            log("Symbol files unchanged. Skipping re-processing.")
            return cache.get("symbols", {})

    symbols = parse_symbols(paths)
    write_json_atomic(SYMBOL_CACHE_FILE, {"fingerprint": fp, "symbols": symbols})
    log(f"Processed symbol files. Symbols loaded: {len(symbols)}")
    return symbols


def init_db():
    global db

    db = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS first_closes (
            symbol TEXT NOT NULL,
            day TEXT NOT NULL,
            exchange TEXT NOT NULL,
            token TEXT NOT NULL,
            tsym TEXT NOT NULL,
            first_1m_close REAL,
            first_5m_close REAL,
            first_15m_close REAL,
            fetch_done INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(symbol, day)
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_first_closes_day ON first_closes(day)")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS history_state (
            symbol TEXT PRIMARY KEY,
            next_day TEXT NOT NULL,
            empty_streak INTEGER NOT NULL DEFAULT 0,
            lookback_days INTEGER NOT NULL DEFAULT 0,
            retries INTEGER NOT NULL DEFAULT 0,
            done INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_history_state_done ON history_state(done)")
    db.commit()


def db_upsert_first_close(symbol, info, day_s, row_vals, fetch_done):
    db.execute(
        """
        INSERT INTO first_closes(
            symbol, day, exchange, token, tsym,
            first_1m_close, first_5m_close, first_15m_close,
            fetch_done, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, day) DO UPDATE SET
            exchange=excluded.exchange,
            token=excluded.token,
            tsym=excluded.tsym,
            first_1m_close=excluded.first_1m_close,
            first_5m_close=excluded.first_5m_close,
            first_15m_close=excluded.first_15m_close,
            fetch_done=excluded.fetch_done,
            updated_at=excluded.updated_at
        """,
        (
            symbol,
            day_s,
            info["exchange"],
            info["token"],
            info["tsym"],
            row_vals.get("first_1m_close"),
            row_vals.get("first_5m_close"),
            row_vals.get("first_15m_close"),
            1 if fetch_done else 0,
            now_iso(),
        ),
    )


def db_load_today(day_s):
    out = {}
    cur = db.execute(
        """
        SELECT symbol, exchange, token, tsym,
               first_1m_close, first_5m_close, first_15m_close,
               fetch_done, updated_at
        FROM first_closes WHERE day = ?
        """,
        (day_s,),
    )
    for r in cur.fetchall():
        out[r[0]] = {
            "symbol": r[0],
            "exchange": r[1],
            "token": r[2],
            "tsym": r[3],
            "first_1m_close": r[4],
            "first_5m_close": r[5],
            "first_15m_close": r[6],
            "fetch_done": bool(r[7]),
            "updated_at": r[8],
        }
    return out


def db_seed_history_state(symbols, start_day_s):
    ts = now_iso()
    rows = [(s, start_day_s, 0, 0, 0, 0, ts) for s in symbols]
    db.executemany(
        """
        INSERT OR IGNORE INTO history_state(
            symbol, next_day, empty_streak, lookback_days, retries, done, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    db.commit()


def db_get_history_batch(limit_n):
    cur = db.execute(
        """
        SELECT symbol, next_day, empty_streak, lookback_days, retries
        FROM history_state WHERE done = 0 LIMIT ?
        """,
        (limit_n,),
    )
    return cur.fetchall()


def db_update_history_state(symbol, next_day, empty_streak, lookback_days, retries, done):
    db.execute(
        """
        UPDATE history_state
        SET next_day=?, empty_streak=?, lookback_days=?, retries=?, done=?, updated_at=?
        WHERE symbol=?
        """,
        (next_day, empty_streak, lookback_days, retries, 1 if done else 0, now_iso(), symbol),
    )


def init_tick_file():
    if TICKS_FILE.exists():
        return
    with TICKS_FILE.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["received_ts", "exchange", "token", "lp", "ft", "ts"])


def compute_target_minutes(day_obj):
    out = {}
    for exch, o in MARKET_OPEN.items():
        t0 = datetime.combine(day_obj, o)
        out[exch] = {
            "m1": t0.strftime("%H:%M"),
            "m5": (t0 + timedelta(minutes=4)).strftime("%H:%M"),
            "m15": (t0 + timedelta(minutes=14)).strftime("%H:%M"),
            "fallback_after": t0 + timedelta(minutes=16),
        }
    return out


def parse_tick_dt(tick):
    ft = tick.get("ft")
    if ft not in (None, ""):
        try:
            v = float(ft)
            if v > 1e12:
                v = v / 1000.0
            return datetime.fromtimestamp(v)
        except Exception:
            pass
    return datetime.now()


def mark_today_dirty(symbol):
    global _ui_dirty
    dirty_today.add(symbol)
    _ui_dirty = True


def ensure_today_row(symbol, info):
    row = today_rows.get(symbol)
    if row:
        return row
    row = {
        "symbol": symbol,
        "exchange": info["exchange"],
        "token": info["token"],
        "tsym": info["tsym"],
        "first_1m_close": None,
        "first_5m_close": None,
        "first_15m_close": None,
        "fetch_done": False,
        "updated_at": now_iso(),
    }
    today_rows[symbol] = row
    return row


def update_today_from_tick(symbol, info, price, dt_obj):
    if dt_obj.date() != TODAY:
        return False

    minute = dt_obj.strftime("%H:%M")
    tgt = target_minutes.get(info["exchange"], target_minutes["NSE"])

    row = ensure_today_row(symbol, info)
    changed = False

    if minute == tgt["m1"] and row.get("first_1m_close") != price:
        row["first_1m_close"] = price
        changed = True
    elif minute == tgt["m5"] and row.get("first_5m_close") != price:
        row["first_5m_close"] = price
        changed = True
    elif minute == tgt["m15"] and row.get("first_15m_close") != price:
        row["first_15m_close"] = price
        changed = True

    complete = (
        row.get("first_1m_close") is not None
        and row.get("first_5m_close") is not None
        and row.get("first_15m_close") is not None
    )

    if complete and not row.get("fetch_done"):
        row["fetch_done"] = True
        pending_today.discard(symbol)
        changed = True

    if changed:
        row["updated_at"] = now_iso()
        today_fail_counts.pop(symbol, None)
        mark_today_dirty(symbol)

    return changed


def buffer_tick(tick):
    global _ticks_received, _ui_dirty

    exch = tick.get("e", "")
    token = tick.get("tk", "")
    symbol = f"{exch}|{token}"
    info = symbol_map.get(symbol)

    _ticks_received += 1

    lp = tick.get("lp", "")
    if lp not in (None, ""):
        try:
            price = float(lp)
            ltp_map[symbol] = price
            _ui_dirty = True
            if info:
                dt_obj = parse_tick_dt(tick)
                update_today_from_tick(symbol, info, price, dt_obj)
        except Exception:
            pass

    vol_raw = tick.get("v", tick.get("vol", ""))
    if vol_raw not in (None, ""):
        try:
            vol = float(vol_raw)
            prev = volume_map.get(symbol)
            if prev != vol:
                volume_map[symbol] = vol
                _ui_dirty = True
        except Exception:
            pass

    _tick_buffer.append([
        int(time.time()),
        exch,
        token,
        lp,
        tick.get("ft", ""),
        tick.get("ts", ""),
    ])


def flush_ticks(force=False):
    global _ticks_flushed, _last_tick_flush_ts

    if not _tick_buffer:
        return 0

    now_t = time.time()
    if not force and len(_tick_buffer) < TICK_FLUSH_SIZE and (now_t - _last_tick_flush_ts) < TICK_FLUSH_INTERVAL_SEC:
        return 0

    rows = list(_tick_buffer)
    _tick_buffer.clear()

    with TICKS_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    _ticks_flushed += len(rows)
    _last_tick_flush_ts = now_t
    return len(rows)


def flush_today_dirty(max_rows):
    if not dirty_today:
        return 0

    keys = list(dirty_today)
    if max_rows > 0 and len(keys) > max_rows:
        keys = keys[:max_rows]

    for s in keys:
        row = today_rows.get(s)
        info = symbol_map.get(s)
        if row and info:
            db_upsert_first_close(s, info, TODAY_S, row, row.get("fetch_done", False))

    for s in keys:
        dirty_today.discard(s)

    db.commit()
    return len(keys)


def on_feed_update(tick):
    with lock:
        buffer_tick(tick)


def on_socket_open():
    global socket_opened
    socket_opened = True
    log("WebSocket connected")


def build_rest_clients(creds, usertoken):
    clients = [api]
    target = max(1, min(MAX_REST_SESSIONS, FETCH_WORKERS))
    for _ in range(target - 1):
        c = NorenApi(host="https://api.shoonya.com/NorenWClientTP/", websocket="wss://api.shoonya.com/NorenWSTP/")
        try:
            c.set_session(userid=creds["userid"], password=creds["password"], usertoken=usertoken)
            clients.append(c)
        except Exception:
            pass
    return clients


def login():
    global api, rest_clients

    creds = json.loads(CRED_FILE.read_text(encoding="utf-8"))
    api = NorenApi(host="https://api.shoonya.com/NorenWClientTP/", websocket="wss://api.shoonya.com/NorenWSTP/")
    ret = api.login(
        userid=creds["userid"],
        password=creds["password"],
        twoFA=pyotp.TOTP(creds["totp_secret"]).now(),
        vendor_code=creds["vendor_code"],
        api_secret=creds["api_secret"],
        imei=creds["imei"],
    )
    if ret.get("stat") != "Ok":
        raise RuntimeError(f"Login failed: {ret}")

    rest_clients = build_rest_clients(creds, ret.get("susertoken"))
    log(f"Login success | REST sessions: {len(rest_clients)}")


def fetch_window_closes(client, exchange, token, day_obj):
    open_dt = datetime.combine(day_obj, MARKET_OPEN.get(exchange, dtime(9, 15)))
    start_ts = int((open_dt - timedelta(minutes=1)).timestamp())
    end_ts = int((open_dt + timedelta(minutes=30)).timestamp())

    try:
        data = client.get_time_price_series(
            exchange=exchange,
            token=token,
            starttime=start_ts,
            endtime=end_ts,
            interval=1,
        )
    except TypeError:
        data = client.get_time_price_series(exchange, token, starttime=start_ts, endtime=end_ts)
    except Exception:
        return None, False

    if not data:
        return {"first_1m_close": None, "first_5m_close": None, "first_15m_close": None}, True

    dkey = open_dt.strftime("%d-%m-%Y")
    m1 = open_dt.strftime("%H:%M")
    m5 = (open_dt + timedelta(minutes=4)).strftime("%H:%M")
    m15 = (open_dt + timedelta(minutes=14)).strftime("%H:%M")

    c1 = c5 = c15 = None
    if isinstance(data, list):
        for row in data:
            t = str(row.get("time", ""))
            if len(t) < 16 or not t.startswith(dkey):
                continue
            c = row.get("intc")
            if c in (None, ""):
                continue
            try:
                p = float(c)
            except Exception:
                continue

            minute = t[11:16]
            if minute == m1 and c1 is None:
                c1 = p
            elif minute == m5 and c5 is None:
                c5 = p
            elif minute == m15 and c15 is None:
                c15 = p

            if c1 is not None and c5 is not None and c15 is not None:
                break

    return {"first_1m_close": c1, "first_5m_close": c5, "first_15m_close": c15}, True


def subscribe_all_symbols():
    keys = list(symbol_map.keys())
    if MAX_SUBSCRIBE_SYMBOLS > 0 and len(keys) > MAX_SUBSCRIBE_SYMBOLS:
        keys = keys[:MAX_SUBSCRIBE_SYMBOLS]
        log(f"Subscription capped by MAX_SUBSCRIBE_SYMBOLS={MAX_SUBSCRIBE_SYMBOLS}")

    for i in range(0, len(keys), SUBSCRIBE_BATCH_SIZE):
        batch = keys[i : i + SUBSCRIBE_BATCH_SIZE]
        api.subscribe(batch, "d")
        log(f"Subscribed {i + len(batch)} / {len(keys)}")
        time.sleep(SUBSCRIBE_SLEEP_SEC)


def init_today_pending():
    pending_today.clear()
    for symbol, info in symbol_map.items():
        row = today_rows.get(symbol)
        if not row:
            pending_today.add(symbol)
            continue

        complete = (
            row.get("first_1m_close") is not None
            and row.get("first_5m_close") is not None
            and row.get("first_15m_close") is not None
        )
        if complete:
            row["fetch_done"] = True
        else:
            row["fetch_done"] = bool(row.get("fetch_done", False))
            if not row["fetch_done"]:
                pending_today.add(symbol)

    log(f"Current-day pending symbols: {len(pending_today)}")


def today_fallback_loop():
    while True:
        now_dt = datetime.now()
        with lock:
            if not pending_today:
                log("Current-day first-close completed (tick + fallback).")
                return
            candidates = [
                s
                for s in pending_today
                if now_dt >= target_minutes.get(symbol_map[s]["exchange"], target_minutes["NSE"])["fallback_after"]
            ]

        if not candidates:
            time.sleep(CURRENT_DAY_SLEEP_SEC)
            continue

        keys = candidates[:CURRENT_DAY_BATCH]
        done_count = 0

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            fut_map = {}
            for i, s in enumerate(keys):
                info = symbol_map[s]
                client = rest_clients[i % len(rest_clients)]
                fut_map[pool.submit(fetch_window_closes, client, info["exchange"], info["token"], TODAY)] = s

            for i, fut in enumerate(as_completed(fut_map), 1):
                s = fut_map[fut]
                info = symbol_map[s]

                vals, fetched = None, False
                try:
                    vals, fetched = fut.result()
                except Exception:
                    vals, fetched = None, False

                with lock:
                    row = ensure_today_row(s, info)
                    retries = today_fail_counts.get(s, 0)

                    if fetched and vals:
                        if row.get("first_1m_close") is None and vals.get("first_1m_close") is not None:
                            row["first_1m_close"] = vals.get("first_1m_close")
                        if row.get("first_5m_close") is None and vals.get("first_5m_close") is not None:
                            row["first_5m_close"] = vals.get("first_5m_close")
                        if row.get("first_15m_close") is None and vals.get("first_15m_close") is not None:
                            row["first_15m_close"] = vals.get("first_15m_close")

                    complete = (
                        row.get("first_1m_close") is not None
                        and row.get("first_5m_close") is not None
                        and row.get("first_15m_close") is not None
                    )

                    if complete:
                        row["fetch_done"] = True
                        row["updated_at"] = now_iso()
                        pending_today.discard(s)
                        today_fail_counts.pop(s, None)
                        done_count += 1
                    else:
                        retries += 1
                        today_fail_counts[s] = retries
                        if retries >= MAX_FETCH_RETRIES:
                            row["fetch_done"] = False
                            row["updated_at"] = now_iso()
                            pending_today.discard(s)

                    mark_today_dirty(s)

                    if i % FETCH_SAVE_EVERY == 0:
                        flush_today_dirty(TODAY_DB_FLUSH_MAX_ROWS)

        with lock:
            flush_today_dirty(TODAY_DB_FLUSH_MAX_ROWS)
            left = len(pending_today)

        log(f"Today fallback cycle: processed={len(keys)}, finalized={done_count}, remaining={left}")
        time.sleep(CURRENT_DAY_SLEEP_SEC)


def history_loop():
    while True:
        with lock:
            batch = db_get_history_batch(HISTORY_BATCH)

        if not batch:
            log("Historical backfill completed.")
            return

        processed = 0
        with_data = 0

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            fut_map = {}
            for i, row in enumerate(batch):
                symbol, next_day_s, _empty, _lookback, _retries = row
                info = symbol_map.get(symbol)
                if not info:
                    continue
                client = rest_clients[i % len(rest_clients)]
                fut_map[pool.submit(fetch_window_closes, client, info["exchange"], info["token"], date.fromisoformat(next_day_s))] = row

            for i, fut in enumerate(as_completed(fut_map), 1):
                symbol, next_day_s, empty_streak, lookback_days, retries = fut_map[fut]
                info = symbol_map[symbol]

                vals, fetched = None, False
                try:
                    vals, fetched = fut.result()
                except Exception:
                    vals, fetched = None, False

                day_obj = date.fromisoformat(next_day_s)
                next_day_new = (day_obj - timedelta(days=1)).isoformat()

                with lock:
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
                        if retries >= MAX_FETCH_RETRIES:
                            retries = 0
                            lookback_days += 1
                            empty_streak += 1
                        else:
                            next_day_new = next_day_s

                    done = lookback_days >= HISTORY_MAX_LOOKBACK_DAYS or empty_streak >= HISTORY_STOP_EMPTY_STREAK
                    db_update_history_state(symbol, next_day_new, empty_streak, lookback_days, retries, done)

                    if i % FETCH_SAVE_EVERY == 0:
                        db.commit()

                processed += 1

        with lock:
            db.commit()
            left = db.execute("SELECT COUNT(1) FROM history_state WHERE done=0").fetchone()[0]

        log(f"History cycle: processed={processed}, with_data={with_data}, pending_symbols={left}")
        time.sleep(HISTORY_SLEEP_SEC)


def write_ui_snapshot():
    global _ui_dirty, _last_ui_snapshot_ts

    now_t = time.time()
    if now_t - _last_ui_snapshot_ts < UI_SNAPSHOT_INTERVAL_SEC:
        return

    with lock:
        if not _ui_dirty:
            _last_ui_snapshot_ts = now_t
            return
        today_copy = dict(today_rows)
        ltp_copy = dict(ltp_map)
        vol_copy = dict(volume_map)
        order_copy = list(ordered_symbols)
        _ui_dirty = False
        _last_ui_snapshot_ts = now_t

    rows = []
    max_rows = UI_MAX_ROWS if UI_MAX_ROWS > 0 else None

    seen = set()
    for s in order_copy:
        if s not in today_copy and s not in ltp_copy and s not in vol_copy:
            continue
        seen.add(s)
        if max_rows is not None and len(rows) >= max_rows:
            break
        info = symbol_map.get(s, {})
        row = today_copy.get(s, {})
        rows.append(
            {
                "symbol": s,
                "exchange": info.get("exchange", row.get("exchange", "")),
                "token": info.get("token", row.get("token", "")),
                "tsym": info.get("tsym", row.get("tsym", "")),
                "ltp": ltp_copy.get(s),
                "volume": vol_copy.get(s),
                "first_1m_close": row.get("first_1m_close"),
                "first_5m_close": row.get("first_5m_close"),
                "first_15m_close": row.get("first_15m_close"),
                "fetch_done": bool(row.get("fetch_done", False)),
                "updated_at": row.get("updated_at"),
            }
        )

    if max_rows is None or len(rows) < max_rows:
        extra = sorted((set(today_copy.keys()) | set(ltp_copy.keys()) | set(vol_copy.keys())) - seen)
        for s in extra:
            if max_rows is not None and len(rows) >= max_rows:
                break
            info = symbol_map.get(s, {})
            row = today_copy.get(s, {})
            rows.append(
                {
                    "symbol": s,
                    "exchange": info.get("exchange", row.get("exchange", "")),
                    "token": info.get("token", row.get("token", "")),
                    "tsym": info.get("tsym", row.get("tsym", "")),
                    "ltp": ltp_copy.get(s),
                    "volume": vol_copy.get(s),
                    "first_1m_close": row.get("first_1m_close"),
                    "first_5m_close": row.get("first_5m_close"),
                    "first_15m_close": row.get("first_15m_close"),
                    "fetch_done": bool(row.get("fetch_done", False)),
                    "updated_at": row.get("updated_at"),
                }
            )

    payload = {
        "day": TODAY_S,
        "updated_at": now_iso(),
        "row_count": len(rows),
        "rows": rows,
    }
    write_json_atomic(UI_SNAPSHOT_FILE, payload)


def run_forever():
    last_log = time.time()
    last_today_flush = time.time()

    while True:
        time.sleep(1)

        with lock:
            flush_ticks()

        write_ui_snapshot()

        if time.time() - last_today_flush >= TODAY_DB_FLUSH_INTERVAL_SEC:
            with lock:
                flush_today_dirty(TODAY_DB_FLUSH_MAX_ROWS)
            last_today_flush = time.time()

        if time.time() - last_log >= 20:
            with lock:
                left_today = len(pending_today)
                left_history = db.execute("SELECT COUNT(1) FROM history_state WHERE done=0").fetchone()[0]
                buffered = len(_tick_buffer)
                recv = _ticks_received
                stored = _ticks_flushed
                dirty_count = len(dirty_today)
            log(
                f"Live: ticks_received={recv}, ticks_stored={stored}, tick_buffer={buffered}, "
                f"today_pending={left_today}, history_pending={left_history}, today_dirty={dirty_count}"
            )
            last_log = time.time()


def main():
    global symbol_map, ordered_symbols, today_rows, target_minutes

    symbol_map = load_symbols()
    if not symbol_map:
        raise RuntimeError("No symbols found in txt files.")
    ordered_symbols = sorted(symbol_map.keys())

    target_minutes = compute_target_minutes(TODAY)

    init_db()
    with lock:
        today_rows = db_load_today(TODAY_S)
        db_seed_history_state(symbol_map.keys(), YESTERDAY_S)

    init_today_pending()
    init_tick_file()
    login()

    api.start_websocket(subscribe_callback=on_feed_update, socket_open_callback=on_socket_open)
    for _ in range(40):
        if socket_opened:
            break
        time.sleep(0.25)
    if not socket_opened:
        raise RuntimeError("WebSocket did not open.")

    subscribe_all_symbols()

    Thread(target=today_fallback_loop, daemon=True).start()
    Thread(target=history_loop, daemon=True).start()

    run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        with lock:
            flush_ticks(force=True)
            # Final flush of dirty today rows.
            while dirty_today:
                flush_today_dirty(0)
            db.commit()
            db.close()
        log("Stopped by user")





