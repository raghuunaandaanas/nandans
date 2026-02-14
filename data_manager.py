#!/usr/bin/env python3
"""
DATA MANAGER - Comprehensive Historical Data System
====================================================
Handles:
1. Symbol lifecycle (expiry tracking)
2. Continuous backfill for all timeframes
3. 1-minute candle building
4. B5 backtesting engine

Usage:
    python data_manager.py --backfill-all    # Fill all missing data
    python data_manager.py --update          # Update recent data only
    python data_manager.py --build-candles   # Build 1min candles from ticks
    python data_manager.py --backtest SYMBOL # Backtest B5 on symbol
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, List, Dict

# Import from historyapp
sys.path.insert(0, str(Path(__file__).parent))
from historyapp import (
    login, symbol_map, rest_clients,
    fetch_window_closes,
    init_db as historyapp_init_db, load_symbols
)
import historyapp

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_FILE = Path(__file__).parent / "history_out" / "market_data.db"
CRED_FILE = Path(__file__).parent / "shoonya_cred.json"

# =============================================================================
# DATABASE SCHEMA
# =============================================================================

SCHEMA = """
-- Symbol master with expiry tracking
CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    exchange TEXT NOT NULL,
    token TEXT NOT NULL,
    tsym TEXT NOT NULL,
    instrument_type TEXT,  -- FUTIDX, OPTIDX, FUTSTK, OPTSTK, etc
    underlying TEXT,       -- NIFTY, BANKNIFTY, RELIANCE, etc
    expiry_date TEXT,      -- YYYY-MM-DD
    strike_price REAL,     -- For options
    option_type TEXT,      -- CE/PE for options
    lot_size INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_expired INTEGER DEFAULT 0
);

-- First closes (1m, 5m, 15m)
CREATE TABLE IF NOT EXISTS first_closes (
    symbol TEXT NOT NULL,
    day TEXT NOT NULL,
    first_1m_open REAL,
    first_1m_high REAL,
    first_1m_low REAL,
    first_1m_close REAL,
    first_5m_open REAL,
    first_5m_high REAL,
    first_5m_low REAL,
    first_5m_close REAL,
    first_15m_open REAL,
    first_15m_high REAL,
    first_15m_low REAL,
    first_15m_close REAL,
    first_1m_volume INTEGER,
    first_5m_volume INTEGER,
    first_15m_volume INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(symbol, day)
);

-- 1-minute candles for backtesting
CREATE TABLE IF NOT EXISTS candles_1m (
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    PRIMARY KEY(symbol, timestamp)
) WITHOUT ROWID;

-- Ticks (raw data)
CREATE TABLE IF NOT EXISTS ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    price REAL NOT NULL,
    qty INTEGER,
    side TEXT,  -- Buy/Sell
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Backfill status per symbol
CREATE TABLE IF NOT EXISTS backfill_status (
    symbol TEXT PRIMARY KEY,
    last_backfill_day TEXT,
    total_days INTEGER DEFAULT 0,
    missing_days INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- pending, active, complete
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_symbols_expiry ON symbols(expiry_date);
CREATE INDEX IF NOT EXISTS idx_symbols_underlying ON symbols(underlying);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_ts ON candles_1m(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_first_closes_day ON first_closes(day);
"""

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SymbolInfo:
    symbol: str
    exchange: str
    token: str
    tsym: str
    instrument_type: str
    underlying: str
    expiry_date: Optional[str]
    strike_price: Optional[float]
    option_type: Optional[str]

@dataclass 
class OHLCV:
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime

# =============================================================================
# DATABASE MANAGER
# =============================================================================

class DataManager:
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize database with schema"""
        os.makedirs(self.db_path.parent, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        print(f"Database initialized: {self.db_path}")
    
    def sync_symbols(self, symbol_list: List[Dict]):
        """Sync symbol list with database, track new and expired"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        # Get existing symbols
        cursor.execute("SELECT symbol, is_expired FROM symbols")
        existing = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Parse and insert/update symbols
        for sym_data in symbol_list:
            symbol = sym_data.get("symbol")
            if not symbol:
                continue
            
            # Parse symbol details
            parsed = self._parse_symbol(symbol, sym_data)
            
            if symbol in existing:
                # Update last_seen_at
                cursor.execute("""
                    UPDATE symbols SET 
                        last_seen_at = ?,
                        is_expired = 0
                    WHERE symbol = ?
                """, (now, symbol))
            else:
                # Insert new symbol
                cursor.execute("""
                    INSERT INTO symbols 
                    (symbol, exchange, token, tsym, instrument_type, underlying, 
                     expiry_date, strike_price, option_type, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, parsed.exchange, parsed.token, parsed.tsym,
                    parsed.instrument_type, parsed.underlying,
                    parsed.expiry_date, parsed.strike_price, parsed.option_type,
                    now
                ))
        
        # Mark missing symbols as expired
        current_symbols = {s.get("symbol") for s in symbol_list if s.get("symbol")}
        for sym in existing:
            if sym not in current_symbols and not existing[sym]:
                cursor.execute("""
                    UPDATE symbols SET is_expired = 1 WHERE symbol = ?
                """, (sym,))
        
        self.conn.commit()
        print(f"Symbols synced: {len(symbol_list)} active")
    
    def _parse_symbol(self, symbol: str, data: Dict) -> SymbolInfo:
        """Parse symbol details from tsym"""
        tsym = data.get("tsym", "")
        parts = symbol.split("|")
        exchange = parts[0] if len(parts) > 0 else ""
        token = parts[1] if len(parts) > 1 else ""
        
        # Parse instrument type and expiry from tsym
        # Example: NIFTY26FEB25FUT, NIFTY26FEB2517000CE
        instrument_type = ""
        underlying = ""
        expiry_date = None
        strike_price = None
        option_type = None
        
        if "FUT" in tsym:
            instrument_type = "FUTIDX" if any(x in tsym for x in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"]) else "FUTSTK"
            underlying = tsym.split("26")[0] if "26" in tsym else tsym.split("27")[0] if "27" in tsym else tsym[:tsym.find("FUT")-6] if "FUT" in tsym else tsym
        elif "CE" in tsym or "PE" in tsym:
            instrument_type = "OPTIDX" if any(x in tsym for x in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"]) else "OPTSTK"
            option_type = "CE" if "CE" in tsym else "PE"
            # Extract strike
            import re
            match = re.search(r'(\d+)(CE|PE)$', tsym)
            if match:
                strike_price = float(match.group(1))
                underlying = tsym[:tsym.find(match.group(1))]
        
        return SymbolInfo(
            symbol=symbol,
            exchange=exchange,
            token=token,
            tsym=tsym,
            instrument_type=instrument_type,
            underlying=underlying or tsym,
            expiry_date=None,  # Will parse from tsym
            strike_price=strike_price,
            option_type=option_type
        )
    
    def get_symbols_needing_backfill(self, days: int = 365) -> List[str]:
        """Get symbols that need historical backfill"""
        cursor = self.conn.cursor()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT s.symbol FROM symbols s
            LEFT JOIN backfill_status b ON s.symbol = b.symbol
            WHERE s.is_expired = 0
            AND (b.last_backfill_day IS NULL OR b.last_backfill_day < ?)
            ORDER BY s.last_seen_at DESC
            LIMIT 10000
        """, (cutoff,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def save_first_closes(self, symbol: str, day: str, data: Dict):
        """Save first closes data"""
        self.conn.execute("""
            INSERT INTO first_closes 
            (symbol, day, first_1m_open, first_1m_high, first_1m_low, first_1m_close,
             first_5m_open, first_5m_high, first_5m_low, first_5m_close,
             first_15m_open, first_15m_high, first_15m_low, first_15m_close,
             first_1m_volume, first_5m_volume, first_15m_volume, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(symbol, day) DO UPDATE SET
                first_1m_open=excluded.first_1m_open,
                first_1m_high=excluded.first_1m_high,
                first_1m_low=excluded.first_1m_low,
                first_1m_close=excluded.first_1m_close,
                first_5m_open=excluded.first_5m_open,
                first_5m_high=excluded.first_5m_high,
                first_5m_low=excluded.first_5m_low,
                first_5m_close=excluded.first_5m_close,
                first_15m_open=excluded.first_15m_open,
                first_15m_high=excluded.first_15m_high,
                first_15m_low=excluded.first_15m_low,
                first_15m_close=excluded.first_15m_close,
                first_1m_volume=excluded.first_1m_volume,
                first_5m_volume=excluded.first_5m_volume,
                first_15m_volume=excluded.first_15m_volume,
                updated_at=datetime('now')
        """, (
            symbol, day,
            data.get('1m', {}).get('open'), data.get('1m', {}).get('high'),
            data.get('1m', {}).get('low'), data.get('1m', {}).get('close'),
            data.get('5m', {}).get('open'), data.get('5m', {}).get('high'),
            data.get('5m', {}).get('low'), data.get('5m', {}).get('close'),
            data.get('15m', {}).get('open'), data.get('15m', {}).get('high'),
            data.get('15m', {}).get('low'), data.get('15m', {}).get('close'),
            data.get('1m', {}).get('volume'), data.get('5m', {}).get('volume'),
            data.get('15m', {}).get('volume')
        ))
        self.conn.commit()
    
    def save_candle(self, symbol: str, candle: OHLCV):
        """Save 1-minute candle"""
        self.conn.execute("""
            INSERT INTO candles_1m (symbol, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timestamp) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
        """, (symbol, candle.timestamp.isoformat(), candle.open, candle.high,
              candle.low, candle.close, candle.volume))
    
    def save_tick(self, symbol: str, price: float, qty: int, side: str, timestamp: datetime):
        """Save tick"""
        self.conn.execute("""
            INSERT INTO ticks (symbol, timestamp, price, qty, side)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, timestamp.isoformat(), price, qty, side))
    
    def get_backfill_summary(self):
        """Get backfill status summary"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_expired = 0 THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN is_expired = 1 THEN 1 ELSE 0 END) as expired
            FROM symbols
        """)
        total, active, expired = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(DISTINCT symbol) FROM first_closes
        """)
        with_data = cursor.fetchone()[0]
        
        return {
            'total_symbols': total,
            'active_symbols': active,
            'expired_symbols': expired,
            'symbols_with_first_closes': with_data
        }

# =============================================================================
# BACKFILL ENGINE
# =============================================================================

class BackfillEngine:
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
        self.sessions = []
    
    def init_sessions(self, count: int = 8):
        """Initialize API sessions"""
        print(f"Initializing {count} API sessions...")
        
        # Load credentials
        creds = json.loads(CRED_FILE.read_text())
        
        # First login
        historyapp.symbol_map.update(load_symbols())
        historyapp_init_db()
        login()
        
        self.sessions = historyapp.rest_clients
        print(f"Active sessions: {len(self.sessions)}")
        return len(self.sessions) > 0
    
    def backfill_symbol_day(self, symbol: str, day: date) -> bool:
        """Backfill a single symbol for a single day"""
        info = historyapp.symbol_map.get(symbol)
        if not info:
            return False
        
        day_str = day.isoformat()
        exchange = info["exchange"]
        token = info["token"]
        
        # Use round-robin session selection
        session = self.sessions[hash(symbol) % len(self.sessions)]
        
        try:
            vals, fetched = fetch_window_closes(session, exchange, token, day)
            if fetched and vals:
                self.dm.save_first_closes(symbol, day_str, {
                    '1m': {'close': vals.get('first_1m_close')},
                    '5m': {'close': vals.get('first_5m_close')},
                    '15m': {'close': vals.get('first_15m_close')}
                })
                return True
        except Exception as e:
            pass
        
        return False
    
    def backfill_all(self, days: int = 365):
        """Backfill all symbols for all days"""
        symbols = self.dm.get_symbols_needing_backfill(days)
        print(f"Backfilling {len(symbols)} symbols for {days} days...")
        
        # Process day by day
        today = date.today()
        for day_offset in range(days):
            day = today - timedelta(days=day_offset)
            if day.weekday() >= 5:  # Skip weekends
                continue
            
            print(f"\nDay: {day.isoformat()}")
            
            # Process symbols in parallel
            with ThreadPoolExecutor(max_workers=50) as pool:
                futures = {pool.submit(self.backfill_symbol_day, sym, day): sym for sym in symbols[:1000]}
                
                completed = 0
                for future in as_completed(futures):
                    if future.result():
                        completed += 1
                
                print(f"  Completed: {completed}/{len(futures)}")

# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--sync-symbols', action='store_true', help='Sync symbol list')
    parser.add_argument('--backfill-all', action='store_true', help='Backfill all data')
    parser.add_argument('--status', action='store_true', help='Show status')
    args = parser.parse_args()
    
    dm = DataManager()
    
    if args.status or not any([args.init, args.sync_symbols, args.backfill_all]):
        summary = dm.get_backfill_summary()
        print("=" * 60)
        print("DATA MANAGER STATUS")
        print("=" * 60)
        print(f"Total symbols: {summary['total_symbols']}")
        print(f"Active symbols: {summary['active_symbols']}")
        print(f"Expired symbols: {summary['expired_symbols']}")
        print(f"Symbols with data: {summary['symbols_with_first_closes']}")
        print("=" * 60)
    
    if args.sync_symbols:
        # Load symbols from historyapp
        historyapp.symbol_map.update(load_symbols())
        symbol_list = [{'symbol': k, **v} for k, v in historyapp.symbol_map.items()]
        dm.sync_symbols(symbol_list)
    
    if args.backfill_all:
        engine = BackfillEngine(dm)
        if engine.init_sessions():
            engine.backfill_all(days=30)

if __name__ == "__main__":
    main()
