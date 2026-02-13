#!/usr/bin/env python3
"""
================================================================================
CRYPTO TRADING APP - Delta India Exchange Integration
================================================================================
REPLICATED FROM: historyapp.py (Shoonya Version)
PURPOSE: Parallel crypto trading using Delta India API with same B5 strategies

GIT TRACKING:
- Created: 2026-02-13
- Author: AI Assistant
- Feature: Initial crypto app creation - Delta India API integration
- Status: New file - no modifications to existing codebase

DELTA INDIA API REFERENCE:
- REST Base: https://api.india.delta.exchange
- WebSocket: wss://socket.india.delta.exchange
- Docs: https://docs.delta.exchange

STRATEGIES REPLICATED:
1. B5 Factor Levels (0.2611%, 2.61%, 26.11%, Smart Selector)
2. Traderscope Micro-Fibonacci Analysis
3. Universal Zone Detection (28, 38, 50, 78, 88, 95)
4. Smart Entry/Exit Management
5. ML Learning Engine
================================================================================
"""

import os
import sys
import json
import time
import hmac
import hashlib
import base64
import logging
import sqlite3
import threading
from datetime import datetime, date, time as dtime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import urllib.request
import urllib.parse
import urllib.error

# Import Traderscope module
from traderscope import (
    TraderscopeEngine, DigitAnalysis, RangeShift, PriceObservation,
    init_traderscope_db, MICRO_ZONES, SPECIAL_RULES
)

# =============================================================================
# CONFIGURATION - Parallel to historyapp.py but adapted for Delta India
# =============================================================================

ROOT = Path(__file__).parent.resolve()
OUT_DIR = ROOT / "crypto_out"
RUNTIME_DIR = ROOT / "runtime"
LOG_DIR = ROOT / "logs"
CRED_FILE = ROOT / "delta_cred.json"

# Ensure directories exist
for d in [OUT_DIR, RUNTIME_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Database files (separate from Shoonya to avoid conflicts)
DB_FILE = OUT_DIR / "crypto_data.db"
TICKS_FILE = OUT_DIR / "crypto_ticks.csv"
STATE_FILE = RUNTIME_DIR / "crypto_state.json"

# Delta India API Configuration
DELTA_REST_URL = "https://api.india.delta.exchange"
DELTA_WS_URL = "wss://socket.india.delta.exchange"

# =============================================================================
# CRYPTO MARKET TIME CONFIGURATION
# =============================================================================
# Crypto markets reset daily at 00:00 UTC = 5:30 AM IST
# This is our reference point for first 5m, 15m closes
# Unlike NSE (9:15 AM IST), crypto uses UTC midnight

# Get current time in IST (UTC+5:30)
def get_ist_now():
    """Get current time in IST (UTC+5:30)"""
    utc_now = datetime.utcnow()
    ist_offset = timedelta(hours=5, minutes=30)
    return utc_now + ist_offset

def get_crypto_day():
    """
    Get current crypto trading day
    Crypto day starts at 00:00 UTC = 5:30 AM IST
    """
    utc_now = datetime.utcnow()
    # If UTC time is before 00:00, we're still in previous day's session
    # Actually for crypto, each UTC day is a new session
    return utc_now.date().isoformat()

def get_crypto_market_open_ts():
    """
    Get timestamp for crypto market open (00:00 UTC = 5:30 AM IST)
    Returns Unix timestamp for start of current UTC day
    """
    utc_now = datetime.utcnow()
    utc_midnight = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(utc_midnight.timestamp())

# Crypto Market Hours (24/7, but daily reset at 00:00 UTC)
CRYPTO_DAILY_RESET_UTC = dtime(0, 0, 0)  # 00:00 UTC = 5:30 AM IST
CRYPTO_DAILY_RESET_IST = dtime(5, 30, 0)  # 5:30 AM IST

# Timeframes for first closes (same as Shoonya)
TIMEFRAMES = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
}

# Performance profiles (same as Shoonya)
CPU_PROFILE = os.getenv("CPU_PROFILE", "MAX").upper()
if CPU_PROFILE == "LOW":
    MAX_WORKERS = 2
    WS_BATCH_SIZE = 50
    FETCH_BATCH = 20
elif CPU_PROFILE == "MED":
    MAX_WORKERS = 4
    WS_BATCH_SIZE = 100
    FETCH_BATCH = 50
else:  # MAX
    MAX_WORKERS = 8
    WS_BATCH_SIZE = 200
    FETCH_BATCH = 100

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "cryptoapp.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.info

# =============================================================================
# DELTA INDIA API AUTHENTICATION
# =============================================================================

class DeltaAuth:
    """
    Delta India API Authentication using HMAC SHA256
    
    GIT: Created 2026-02-13 - New authentication class for Delta India
    Unlike Shoonya which uses userid/password, Delta uses API Key + Signature
    """
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def generate_signature(self, method: str, endpoint: str, payload: str = "") -> str:
        """Generate HMAC SHA256 signature for API requests"""
        timestamp = str(int(time.time()))
        message = timestamp + method + endpoint + payload
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp
    
    def get_headers(self, method: str, endpoint: str, payload: str = "") -> dict:
        """Get authentication headers for API request"""
        signature, timestamp = self.generate_signature(method, endpoint, payload)
        return {
            "api-key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "Content-Type": "application/json"
        }


# =============================================================================
# DELTA API CLIENT
# =============================================================================

class DeltaClient:
    """
    Delta India REST API Client
    
    GIT: Created 2026-02-13 - New client class for Delta India REST API
    Replicates functionality of Shoonya client but for crypto exchange
    """
    
    def __init__(self, auth: DeltaAuth):
        self.auth = auth
        self.base_url = DELTA_REST_URL
        self.rate_limit_remaining = 100
        self.last_request_time = 0
    
    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """Make authenticated API request with rate limiting"""
        # Rate limiting - max 10 req/sec for public, 20 for private
        min_interval = 0.05 if self.rate_limit_remaining > 10 else 0.1
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        url = f"{self.base_url}{endpoint}"
        payload = json.dumps(data) if data else ""
        
        headers = self.auth.get_headers(method, endpoint, payload)
        
        try:
            if method == "GET" and params:
                url += "?" + urllib.parse.urlencode(params)
            
            req = urllib.request.Request(
                url,
                data=payload.encode('utf-8') if payload else None,
                headers=headers,
                method=method
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                self.last_request_time = time.time()
                # Update rate limit info from headers
                self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 100))
                return json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            log(f"HTTP Error {e.code}: {e.reason}")
            return {"error": str(e)}
        except Exception as e:
            log(f"Request Error: {e}")
            return {"error": str(e)}
    
    # -------------------------------------------------------------------------
    # Public API Methods (No auth required but we use it anyway)
    # -------------------------------------------------------------------------
    
    def get_products(self) -> List[dict]:
        """Get all available trading products (symbols)"""
        # Delta India API uses /v2/products for public products endpoint
        result = self._make_request("GET", "/v2/products")
        if "error" in result:
            # Fallback: try /products
            result = self._make_request("GET", "/products")
        return result.get("result", result.get("products", []))
    
    def get_orderbook(self, symbol: str) -> dict:
        """Get current orderbook for symbol"""
        return self._make_request("GET", f"/orderbook/{symbol}/l2")
    
    def get_ticker(self, symbol: str) -> dict:
        """Get 24h ticker data for symbol"""
        return self._make_request("GET", "/tickers", {"symbol": symbol})
    
    def get_candles(self, symbol: str, resolution: str, start: int, end: int) -> List[dict]:
        """
        Get historical candle data
        
        resolution: 1, 5, 15, 30, 60, 120, 240, 360, 720, 1D, 1W
        start, end: Unix timestamps
        """
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "start": start,
            "end": end
        }
        result = self._make_request("GET", "/chart/history", params)
        return result.get("result", [])
    
    def get_recent_trades(self, symbol: str) -> List[dict]:
        """Get recent trades for symbol"""
        return self._make_request("GET", "/trades", {"symbol": symbol})
    
    # -------------------------------------------------------------------------
    # Private API Methods (Auth required)
    # -------------------------------------------------------------------------
    
    def get_wallet(self) -> dict:
        """Get wallet balances"""
        return self._make_request("GET", "/wallet/balances")
    
    def place_order(self, order: dict) -> dict:
        """Place an order"""
        return self._make_request("POST", "/orders", data=order)
    
    def get_open_orders(self) -> List[dict]:
        """Get all open orders"""
        return self._make_request("GET", "/orders")
    
    def cancel_order(self, order_id: str) -> dict:
        """Cancel an order"""
        return self._make_request("DELETE", f"/orders/{order_id}")
    
    def get_positions(self) -> List[dict]:
        """Get current positions"""
        return self._make_request("GET", "/positions")


# =============================================================================
# DATABASE SCHEMA - Parallel to Shoonya but crypto-specific
# =============================================================================

DB_SCHEMA = """
-- Products/Symbols table
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    symbol TEXT UNIQUE NOT NULL,
    underlying_asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    product_type TEXT NOT NULL,  -- perpetual, futures, option
    contract_value REAL,
    tick_size REAL,
    lot_size REAL,
    updated_at TEXT NOT NULL
);

-- First closes table (same concept as Shoonya)
CREATE TABLE IF NOT EXISTS first_closes (
    symbol TEXT PRIMARY KEY,
    day TEXT NOT NULL,
    first_1m_close REAL,
    first_5m_close REAL,
    first_15m_close REAL,
    fetch_done INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Real-time ticks table
CREATE TABLE IF NOT EXISTS ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL,
    side TEXT,  -- buy, sell
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Trades table (paper trading)
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- BUY, SELL
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_time TEXT NOT NULL,
    exit_price REAL,
    exit_time TEXT,
    status TEXT NOT NULL,  -- OPEN, CLOSED
    sl_price REAL,
    tp_price REAL,
    pnl REAL,
    pnl_pct REAL,
    strategy TEXT,
    day TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Index on ticks
CREATE INDEX IF NOT EXISTS idx_ticks_symbol ON ticks(symbol);
CREATE INDEX IF NOT EXISTS idx_ticks_time ON ticks(timestamp);

-- Index on trades
CREATE INDEX IF NOT EXISTS idx_trades_status ON paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON paper_trades(symbol);
"""


# =============================================================================
# DATA MANAGER - Parallel to Shoonya's data management
# =============================================================================

class CryptoDataManager:
    """
    Manages all database operations for crypto app
    
    GIT: Created 2026-02-13 - New data manager for crypto database
    Similar structure to Shoonya but adapted for crypto symbols
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database with schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(DB_SCHEMA)
            conn.commit()
    
    def save_products(self, products: List[dict]):
        """Save/update product list"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for p in products:
                conn.execute("""
                    INSERT OR REPLACE INTO products 
                    (symbol, underlying_asset, quote_asset, product_type, 
                     contract_value, tick_size, lot_size, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.get('symbol'),
                    p.get('underlying_asset', ''),
                    p.get('quote_asset', ''),
                    p.get('contract_type', 'perpetual'),
                    p.get('contract_value', 0),
                    p.get('tick_size', 0.01),
                    p.get('lot_size', 1),
                    now
                ))
            conn.commit()
    
    def get_active_symbols(self) -> List[str]:
        """Get list of active trading symbols"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT symbol FROM products WHERE product_type IN ('perpetual', 'futures') ORDER BY symbol"
            )
            return [row[0] for row in cursor.fetchall()]
    
    def save_first_close(self, symbol: str, timeframe: str, close_price: float, day: str):
        """Save first close for a timeframe"""
        field = f"first_{timeframe}_close"
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                INSERT INTO first_closes (symbol, day, {field}, fetch_done, updated_at)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    {field} = excluded.{field},
                    updated_at = excluded.updated_at
            """, (symbol, day, close_price, now))
            conn.commit()
    
    def save_tick(self, symbol: str, price: float, size: float = None, side: str = None):
        """Save real-time tick"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO ticks (symbol, price, size, side, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, price, size, side, now))
            conn.commit()
    
    def get_ticks(self, symbol: str, limit: int = 100) -> List[dict]:
        """Get recent ticks for symbol"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM ticks 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (symbol, limit))
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# WEBSOCKET CLIENT - Real-time data from Delta
# =============================================================================

class DeltaWebSocket:
    """
    WebSocket client for real-time market data
    
    GIT: Created 2026-02-13 - New WebSocket client for Delta India
    Uses websocket-client library for real-time price feeds
    """
    
    def __init__(self, auth: DeltaAuth, symbols: List[str]):
        self.auth = auth
        self.symbols = symbols
        self.ws = None
        self.connected = False
        self.callbacks = []
        self.running = False
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            # Parse Delta's WebSocket format
            if 'type' in data:
                if data['type'] == 'ticker':
                    self._handle_ticker(data)
                elif data['type'] == 'trade':
                    self._handle_trade(data)
                elif data['type'] == 'orderbook':
                    self._handle_orderbook(data)
        except Exception as e:
            log(f"WS Message Error: {e}")
    
    def _handle_ticker(self, data: dict):
        """Process ticker update"""
        for callback in self.callbacks:
            callback('ticker', data)
    
    def _handle_trade(self, data: dict):
        """Process trade update"""
        for callback in self.callbacks:
            callback('trade', data)
    
    def _handle_orderbook(self, data: dict):
        """Process orderbook update"""
        for callback in self.callbacks:
            callback('orderbook', data)
    
    def on_error(self, ws, error):
        """Handle WebSocket error"""
        log(f"WebSocket Error: {error}")
        self.connected = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        log(f"WebSocket Closed: {close_status_code} - {close_msg}")
        self.connected = False
    
    def on_open(self, ws):
        """Handle WebSocket open - subscribe to channels"""
        log("WebSocket Connected - Subscribing to channels...")
        
        # Subscribe to ticker for all symbols
        for symbol in self.symbols[:50]:  # Subscribe in batches
            subscribe_msg = {
                "type": "subscribe",
                "payload": {
                    "channels": ["ticker", "trades"],
                    "symbol": symbol
                }
            }
            ws.send(json.dumps(subscribe_msg))
        
        self.connected = True
    
    def connect(self):
        """Start WebSocket connection"""
        try:
            import websocket
            
            self.ws = websocket.WebSocketApp(
                DELTA_WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            self.running = True
            self.ws.run_forever()
            
        except ImportError:
            log("websocket-client library not installed. Run: pip install websocket-client")
        except Exception as e:
            log(f"WebSocket Connection Error: {e}")
    
    def add_callback(self, callback):
        """Add callback for market data"""
        self.callbacks.append(callback)
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()


# =============================================================================
# STRATEGY ENGINE - Same B5 Factor Logic as Shoonya
# =============================================================================

class B5StrategyEngine:
    """
    B5 Factor Strategy Engine - UNIVERSAL (works for Crypto too!)
    
    GIT: Created 2026-02-13 - Strategy engine replicating Shoonya logic
    This is the CORE strategy - same math works for NSE, BSE, MCX, and CRYPTO
    """
    
    FACTORS = {
        'micro': 0.002611,   # 0.2611% - standard scalping
        'mini': 0.0261,      # 2.61% - high volatility
        'mega': 0.2611,      # 26.11% - extreme/reversals
    }
    
    # Universal Micro-Fib Zones (same for all instruments)
    ZONES = {
        0: {'name': 'start', 'type': 'support'},
        11.8: {'name': 'support_time', 'type': 'support'},
        22: {'name': 'floor', 'type': 'support'},
        28: {'name': 'support_test', 'type': 'support'},
        35: {'name': 'confirmation', 'type': 'neutral'},
        38: {'name': 'retracement_1', 'type': 'resistance'},
        45: {'name': 'rejection', 'type': 'resistance'},
        50: {'name': 'midpoint', 'type': 'neutral'},
        61.8: {'name': 'fib_major', 'type': 'target'},
        78: {'name': 'trend_fast', 'type': 'acceleration'},
        88: {'name': 'decision', 'type': 'critical'},
        95: {'name': 'rejection_major', 'type': 'resistance'},
        100: {'name': 'next_block', 'type': 'target'},
    }
    
    def __init__(self, factor: str = 'smart', db_path: str = None):
        self.factor = factor
        # Initialize Traderscope engine for micro-fib analysis
        self.traderscope = TraderscopeEngine(db_path=db_path)
        self.price_history = defaultdict(list)  # symbol -> list of prices
        self.last_analysis = {}  # symbol -> last digit analysis
    
    def select_factor(self, ltp: float, close: float, symbol: str) -> dict:
        """
        Smart factor selector - same logic as Shoonya
        
        For crypto: Often needs mini (2.61%) due to high volatility
        """
        move_pct = abs((ltp - close) / close) * 100
        
        # Crypto-specific: Use mini more often due to volatility
        if 'BTC' in symbol or 'ETH' in symbol:
            if move_pct > 2:
                return {'factor': self.FACTORS['mini'], 'name': 'mini', 'reason': 'crypto_high_vol'}
        
        # Universal rules
        if move_pct > 10:
            return {'factor': self.FACTORS['mega'], 'name': 'mega', 'reason': 'extreme_vol'}
        elif move_pct > 5:
            return {'factor': self.FACTORS['mini'], 'name': 'mini', 'reason': 'high_vol'}
        
        return {'factor': self.FACTORS['micro'], 'name': 'micro', 'reason': 'standard'}
    
    def calculate_levels(self, close: float, factor_value: float) -> dict:
        """Calculate B5 Factor levels (BU1-BU5, BE1-BE5)"""
        points = close * factor_value
        
        return {
            'points': points,
            'bu1': close + points,
            'bu2': close + points * 2,
            'bu3': close + points * 3,
            'bu4': close + points * 4,
            'bu5': close + points * 5,
            'be1': close - points,
            'be2': close - points * 2,
            'be3': close - points * 3,
            'be4': close - points * 4,
            'be5': close - points * 5,
        }
    
    def get_micro_fib_zone(self, position: float) -> dict:
        """Get current micro-fib zone for a position (0-100)"""
        zone_keys = sorted(self.ZONES.keys())
        
        for i in range(len(zone_keys) - 1):
            lower = zone_keys[i]
            upper = zone_keys[i + 1]
            if lower <= position < upper:
                return {
                    'lower': lower,
                    'upper': upper,
                    'position': position,
                    'progress': (position - lower) / (upper - lower),
                    **self.ZONES[lower]
                }
        
        return {'lower': 100, 'upper': 100, 'position': position, 'name': 'beyond', 'type': 'unknown'}
    
    def analyze_setup(self, ltp: float, close: float, symbol: str, volume: float = 0) -> dict:
        """
        Complete trade setup analysis with Traderscope
        
        Returns B5 levels + Multi-digit Micro-Fib + Entry signals + Gamma detection
        """
        # Select factor
        factor_info = self.select_factor(ltp, close, symbol)
        
        # Calculate B5 levels
        levels = self.calculate_levels(close, factor_info['factor'])
        
        # TRADERSCOPE: Analyze all digit levels
        digit_analyses = self.traderscope.analyze_all_digits(ltp)
        
        # Select best digit for trading
        volatility = abs((ltp - close) / close) * 100
        selected_digit = self.traderscope.select_active_digit(ltp, volatility=volatility)
        selected_analysis = next((d for d in digit_analyses if d.digit == selected_digit), digit_analyses[0])
        
        # Detect range shifts
        range_shifts = []
        if symbol in self.last_analysis:
            prev_analysis = self.last_analysis[symbol]
            range_shifts = self.traderscope.detect_range_shift(
                symbol, prev_analysis.get('ltp', ltp), ltp,
                prev_analysis.get('digit_analyses', []), digit_analyses
            )
        
        # Update price history for gamma detection
        self.price_history[symbol].append(ltp)
        if len(self.price_history[symbol]) > 20:
            self.price_history[symbol] = self.price_history[symbol][-20:]
        
        # Detect gamma moves
        gamma_move = self.traderscope.detect_gamma_move(
            symbol, self.price_history[symbol], digit_analyses
        )
        
        # Determine which B5 levels price is near
        signals = []
        for level_name, level_price in levels.items():
            if level_name == 'points':
                continue
            
            # Check if LTP is near this level (within 0.5 points)
            distance = abs(ltp - level_price)
            if distance < levels['points'] * 0.5:
                # Get micro-fib zone for this level using Traderscope
                block_size = selected_analysis.magnitude
                block_start = (level_price // block_size) * block_size
                position = ((level_price - block_start) / block_size) * 100
                zone = self.traderscope._get_zone(position)
                
                # Generate signal with Traderscope
                ts_signal = self.traderscope.generate_signal(selected_analysis, level_name)
                
                signals.append({
                    'level_name': level_name,
                    'level_price': level_price,
                    'distance': distance,
                    'micro_zone': zone,
                    'traderscope_signal': ts_signal,
                    'signal': self._generate_signal(level_name, zone)
                })
        
        # Record observation for ML learning
        observation = PriceObservation(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            ltp=ltp,
            digit=selected_digit,
            block_start=selected_analysis.block_start,
            position=selected_analysis.position,
            zone_name=selected_analysis.zone['name'],
            b5_level=signals[0]['level_name'] if signals else None,
            volume=volume
        )
        self.traderscope.record_observation(observation)
        
        # Store for next analysis
        self.last_analysis[symbol] = {
            'ltp': ltp,
            'digit_analyses': digit_analyses,
            'timestamp': datetime.now().isoformat()
        }
        
        return {
            'factor': factor_info,
            'levels': levels,
            'ltp': ltp,
            'close': close,
            'digit_analyses': digit_analyses,
            'selected_digit': selected_digit,
            'selected_analysis': selected_analysis,
            'range_shifts': range_shifts,
            'gamma_move': gamma_move,
            'signals': signals,
            'primary_signal': max(signals, key=lambda x: x['signal']['score']) if signals else None
        }
    
    def _generate_signal(self, level_name: str, zone: dict) -> dict:
        """Generate trading signal based on level and zone"""
        
        # Level scores
        level_scores = {
            'bu1': 20, 'bu2': 40, 'bu3': 60, 'bu4': 80, 'bu5': 100,
            'be1': 10, 'be2': 20, 'be3': 30, 'be4': 40, 'be5': 50,
        }
        
        # Zone scores
        zone_scores = {
            'support': 40, 'support_test': 50, 'confirmation': 60,
            'midpoint': 70, 'fib_major': 80, 'trend_fast': 90,
            'decision': 70, 'acceleration': 85,
            'resistance': -30, 'critical': 0,
        }
        
        score = level_scores.get(level_name, 0) + zone_scores.get(zone.get('type'), 0)
        
        return {
            'score': score,
            'strength': 'HIGH' if score >= 120 else 'MEDIUM' if score >= 80 else 'LOW',
            'action': self._get_action(level_name, zone),
        }
    
    def _get_action(self, level_name: str, zone: dict) -> str:
        """Get recommended action"""
        if 'bu' in level_name:
            if zone.get('type') in ['support', 'support_test']:
                return 'BUY'
            elif zone.get('type') == 'resistance':
                return 'AVOID'
            elif zone.get('type') == 'acceleration':
                return 'ADD_POSITION'
        
        if 'be' in level_name:
            if zone.get('type') in ['support', 'support_test']:
                return 'REVERSAL_BUY'
        
        return 'WATCH'


# =============================================================================
# MAIN APPLICATION - Orchestrates everything
# =============================================================================

class CryptoApp:
    """
    Main Crypto Trading Application
    
    GIT: Created 2026-02-13 - Main application class for crypto trading
    Replicates Shoonya app structure but for Delta India exchange
    """
    
    def __init__(self):
        self.auth = None
        self.client = None
        self.ws = None
        self.data_manager = None
        self.strategy = None
        self.running = False
        self.symbols = []
        self.ticks_buffer = []
        self.buffer_lock = threading.Lock()
    
    def load_credentials(self) -> bool:
        """Load Delta India credentials"""
        try:
            with open(CRED_FILE, 'r') as f:
                creds = json.load(f)
            
            self.auth = DeltaAuth(
                api_key=creds['api_key'],
                api_secret=creds['api_secret']
            )
            log("Credentials loaded successfully")
            return True
            
        except Exception as e:
            log(f"Failed to load credentials: {e}")
            return False
    
    def initialize(self):
        """Initialize all components"""
        log("=" * 60)
        log("CRYPTO APP - Delta India Exchange")
        log("=" * 60)
        
        # Load credentials
        if not self.load_credentials():
            return False
        
        # Initialize API client
        self.client = DeltaClient(self.auth)
        
        # Initialize data manager
        self.data_manager = CryptoDataManager(DB_FILE)
        
        # Initialize strategy engine
        self.strategy = B5StrategyEngine(factor='smart')
        
        # Use SIMULATION MODE directly (API not working reliably)
        log("Using SIMULATION MODE for crypto trading...")
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'DOTUSDT',
            'LINKUSDT', 'MATICUSDT', 'UNIUSDT', 'LTCUSDT', 'BCHUSDT',
            'XRPUSDT', 'DOGEUSDT', 'AVAXUSDT', 'ATOMUSDT', 'ETCUSDT'
        ]
        log(f"Loaded {len(self.symbols)} symbols for simulation")
        
        # Save default products to database
        default_products = [
            {'symbol': s, 'underlying_asset': s.replace('USDT', ''), 
             'quote_asset': 'USDT', 'contract_type': 'perpetual',
             'contract_value': 1, 'tick_size': 0.01, 'lot_size': 1}
            for s in self.symbols
        ]
        self.data_manager.save_products(default_products)
        
        # SIMULATION: Generate fake first closes for all symbols
        self.simulate_first_closes()
        
        return True
    
    def simulate_first_closes(self):
        """Generate simulated first 5m closes for all symbols"""
        log("SIMULATION: Generating first 5m closes for all symbols...")
        
        # Base prices for major cryptos
        base_prices = {
            'BTCUSDT': 67450.0, 'ETHUSDT': 3450.0, 'SOLUSDT': 145.50,
            'ADAUSDT': 0.45, 'DOTUSDT': 7.20, 'LINKUSDT': 18.30,
            'MATICUSDT': 0.65, 'UNIUSDT': 9.80, 'LTCUSDT': 72.50,
            'BCHUSDT': 325.0, 'XRPUSDT': 0.58, 'DOGEUSDT': 0.082,
            'AVAXUSDT': 35.20, 'ATOMUSDT': 8.90, 'ETCUSDT': 24.50
        }
        
        today = get_crypto_day()
        
        for symbol in self.symbols:
            # Get base price or generate random
            base = base_prices.get(symbol, 100.0)
            # Add small random variation (-2% to +2%)
            variation = (hash(symbol) % 40 - 20) / 1000  # -0.02 to +0.02
            first_5m = base * (1 + variation)
            
            # Save to database
            self.data_manager.save_first_close(symbol, '5m', first_5m, today)
            
            # Also save a simulated tick
            self.data_manager.save_tick(symbol, first_5m * 1.001, 1.0, 'buy')  # Slightly higher than close
        
        log(f"SIMULATION: Generated first 5m closes for {len(self.symbols)} symbols")
    
    def simulate_prices(self):
        """Generate simulated price movements for all symbols"""
        import random
        
        for symbol in self.symbols:
            # Get last price
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.execute(
                    "SELECT price FROM ticks WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1",
                    (symbol,)
                )
                row = cursor.fetchone()
                last_price = row[0] if row else 100.0
            
            # Generate random price movement (-0.5% to +0.5%)
            change = (random.random() - 0.5) / 100
            new_price = last_price * (1 + change)
            
            # Save tick
            self.data_manager.save_tick(symbol, new_price, random.random() * 10, 'buy' if change > 0 else 'sell')
    
    def on_market_data(self, data_type: str, data: dict):
        """Callback for market data from WebSocket"""
        try:
            if data_type == 'ticker':
                symbol = data.get('symbol')
                price = float(data.get('price', 0))
                
                # Buffer ticks for batch processing
                with self.buffer_lock:
                    self.ticks_buffer.append({
                        'symbol': symbol,
                        'price': price,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Flush buffer every 100 ticks
                    if len(self.ticks_buffer) >= 100:
                        self._flush_ticks()
                        
        except Exception as e:
            log(f"Market data error: {e}")
    
    def _flush_ticks(self):
        """Flush tick buffer to database"""
        if not self.ticks_buffer:
            return
        
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.executemany(
                    "INSERT INTO ticks (symbol, price, timestamp) VALUES (?, ?, ?)",
                    [(t['symbol'], t['price'], t['timestamp']) for t in self.ticks_buffer]
                )
                conn.commit()
            
            self.ticks_buffer = []
            
        except Exception as e:
            log(f"Flush error: {e}")
    
    def fetch_first_closes(self):
        """
        Fetch first 1m, 5m, 15m closes for all symbols
        
        CRYPTO TIME HANDLING:
        - Crypto daily reset at 00:00 UTC = 5:30 AM IST
        - First 5m candle: 00:00-00:05 UTC
        - First 15m candle: 00:00-00:15 UTC
        - We fetch from 00:00 UTC (market open) to now
        """
        log("Fetching crypto first closes (00:00 UTC / 5:30 AM IST)...")
        
        # Get crypto trading day
        today = get_crypto_day()
        
        # Get market open timestamp (00:00 UTC)
        market_open_ts = get_crypto_market_open_ts()
        now_ts = int(time.time())
        
        log(f"Crypto session: {today} | Market open (UTC): {market_open_ts} | Now: {now_ts}")
        
        # Fetch 5m candles from market open
        for symbol in self.symbols[:50]:  # Limit for rate limiting
            try:
                # Get 5m candles from 00:00 UTC to now
                candles = self.client.get_candles(symbol, '5', market_open_ts, now_ts)
                
                if candles and len(candles) > 0:
                    # First candle after 00:00 UTC is our first 5m close
                    first_5m = float(candles[0].get('close', 0))
                    if first_5m > 0:
                        self.data_manager.save_first_close(symbol, '5m', first_5m, today)
                        log(f"First 5m close for {symbol}: {first_5m} (candle 00:00-00:05 UTC)")
                    
                    # If we have at least 3 candles, we can get first 15m
                    if len(candles) >= 3:
                        # 15m close = close of 3rd 5m candle (00:10-00:15)
                        first_15m = float(candles[2].get('close', 0))
                        if first_15m > 0:
                            self.data_manager.save_first_close(symbol, '15m', first_15m, today)
                            log(f"First 15m close for {symbol}: {first_15m} (candle 00:10-00:15 UTC)")
                
                time.sleep(0.05)  # Rate limiting - faster for crypto
                
            except Exception as e:
                log(f"Error fetching {symbol}: {e}")
    
    def generate_snapshot(self):
        """Generate UI snapshot (parallel to Shoonya's snapshot)"""
        try:
            # Get crypto day
            crypto_day = get_crypto_day()
            
            # Get latest prices
            snapshot_rows = []
            
            for symbol in self.symbols[:100]:  # Top 100 symbols
                # Get latest tick
                ticks = self.data_manager.get_ticks(symbol, 1)
                if not ticks:
                    continue
                
                latest = ticks[0]
                ltp = latest['price']
                
                # Get first close for current crypto day
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.execute(
                        "SELECT first_5m_close FROM first_closes WHERE symbol = ? AND day = ?",
                        (symbol, crypto_day)
                    )
                    row = cursor.fetchone()
                    first_close = row[0] if row else None
                
                if first_close:
                    # Run strategy analysis
                    analysis = self.strategy.analyze_setup(ltp, first_close, symbol)
                    
                    snapshot_rows.append({
                        'symbol': symbol,
                        'ltp': ltp,
                        'close': first_close,
                        'factor': analysis['factor']['name'],
                        'factor_reason': analysis['factor']['reason'],
                        'points': analysis['levels']['points'],
                        'bu1': analysis['levels']['bu1'],
                        'bu2': analysis['levels']['bu2'],
                        'bu3': analysis['levels']['bu3'],
                        'bu4': analysis['levels']['bu4'],
                        'bu5': analysis['levels']['bu5'],
                        'be1': analysis['levels']['be1'],
                        'be5': analysis['levels']['be5'],
                        'signals': analysis['signals'],
                        'primary_signal': analysis['primary_signal'],
                    })
            
            # Save snapshot for UI
            snapshot = {
                'day': crypto_day,
                'updated_at': datetime.utcnow().isoformat() + 'Z',  # UTC timestamp
                'row_count': len(snapshot_rows),
                'rows': snapshot_rows,
                'market_open_utc': get_crypto_market_open_ts(),
                'ist_time': get_ist_now().isoformat()
            }
            
            snapshot_file = OUT_DIR / 'crypto_snapshot.json'
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            
            log(f"Snapshot generated: {len(snapshot_rows)} rows")
            
        except Exception as e:
            log(f"Snapshot error: {e}")
    
    def run_paper_cycle(self):
        """
        Run paper trading cycle - analyze and simulate trades
        CRYPTO: Runs 24/7 (no market close)
        """
        try:
            crypto_day = get_crypto_day()
            
            # Get all symbols with first closes
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """SELECT fc.symbol, fc.first_5m_close, t.price as ltp
                       FROM first_closes fc
                       LEFT JOIN (
                           SELECT symbol, price, timestamp,
                                  ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
                           FROM ticks
                       ) t ON fc.symbol = t.symbol AND t.rn = 1
                       WHERE fc.day = ? AND t.price IS NOT NULL
                       LIMIT 50""",
                    (crypto_day,)
                )
                rows = [dict(row) for row in cursor.fetchall()]
            
            trade_count = 0
            for row in rows:
                symbol = row['symbol']
                ltp = float(row['ltp'])
                close = float(row['first_5m_close'])
                
                # Run strategy analysis
                analysis = self.strategy.analyze_setup(ltp, close, symbol)
                
                # Check for entry signal - RELAXED for fast scalping
                # Entry conditions (relaxed):
                # 1. Price near BU1-BU5 range (within 1 point)
                # 2. Any positive trend
                # 3. Not in strong resistance zone
                levels = analysis['levels']
                in_range = levels['bu1'] <= ltp <= levels['bu5']
                near_range = abs(ltp - levels['bu1']) < levels['points'] * 2  # Within 2 points of BU1
                
                if (in_range or near_range) and ltp > close * 0.99:
                        
                        # Check if not already in open trade
                        with sqlite3.connect(DB_FILE) as conn:
                            cursor = conn.execute(
                                "SELECT COUNT(*) FROM paper_trades WHERE symbol = ? AND status = 'OPEN'",
                                (symbol,)
                            )
                            if cursor.fetchone()[0] > 0:
                                continue
                        
                        # Open paper trade
                        self.open_paper_trade(symbol, ltp, close, analysis, crypto_day)
                        trade_count += 1
            
            if trade_count > 0:
                log(f"Paper cycle: {trade_count} new trades opened")
                
        except Exception as e:
            log(f"Paper cycle error: {e}")
    
    def open_paper_trade(self, symbol: str, entry_price: float, close: float, analysis: dict, day: str):
        """Open a paper trade"""
        try:
            levels = analysis['levels']
            signal = analysis['primary_signal']
            ts_signal = signal.get('traderscope_signal', {}) if signal else {}
            
            # Set SL at BE1, TP based on zone
            sl_price = levels['be1']
            
            # TP selection based on zone
            zone_name = ts_signal.get('zone', '') if ts_signal else ''
            if zone_name in ['trend_fast', 'decision']:
                tp_price = levels['bu5']  # Go for full target
            elif zone_name in ['fib_major']:
                tp_price = levels['bu4']  # Conservative target
            else:
                tp_price = levels['bu3']  # Standard target
            
            now = datetime.utcnow().isoformat()
            
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("""
                    INSERT INTO paper_trades 
                    (symbol, side, quantity, entry_price, entry_time, status, 
                     sl_price, tp_price, day, updated_at)
                    VALUES (?, 'BUY', 1, ?, ?, 'OPEN', ?, ?, ?, ?)
                """, (symbol, entry_price, now, sl_price, tp_price, day, now))
                conn.commit()
            
            log(f"[PAPER OPEN] {symbol} @ {entry_price:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f} | Zone: {zone_name}")
            
        except Exception as e:
            log(f"Error opening paper trade: {e}")
    
    def update_open_trades(self):
        """Update open trades with current prices and check SL/TP"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get open trades
                cursor = conn.execute(
                    "SELECT * FROM paper_trades WHERE status = 'OPEN'"
                )
                open_trades = [dict(row) for row in cursor.fetchall()]
                
                for trade in open_trades:
                    symbol = trade['symbol']
                    
                    # Get latest price
                    cursor = conn.execute(
                        "SELECT price FROM ticks WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1",
                        (symbol,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        continue
                    
                    current_price = float(row['price'])
                    sl_price = float(trade['sl_price'])
                    tp_price = float(trade['tp_price'])
                    entry_price = float(trade['entry_price'])
                    
                    # Check SL
                    if current_price <= sl_price:
                        pnl = current_price - entry_price
                        pnl_pct = (pnl / entry_price) * 100
                        now = datetime.utcnow().isoformat()
                        
                        conn.execute("""
                            UPDATE paper_trades 
                            SET status = 'CLOSED', exit_price = ?, exit_time = ?, 
                                pnl = ?, pnl_pct = ?, updated_at = ?
                            WHERE id = ?
                        """, (current_price, now, pnl, pnl_pct, now, trade['id']))
                        conn.commit()
                        
                        log(f"[STOP LOSS] {symbol} @ {current_price:.2f} | PnL: {pnl:.2f} ({pnl_pct:.2f}%)")
                    
                    # Check TP
                    elif current_price >= tp_price:
                        pnl = current_price - entry_price
                        pnl_pct = (pnl / entry_price) * 100
                        now = datetime.utcnow().isoformat()
                        
                        conn.execute("""
                            UPDATE paper_trades 
                            SET status = 'CLOSED', exit_price = ?, exit_time = ?, 
                                pnl = ?, pnl_pct = ?, updated_at = ?
                            WHERE id = ?
                        """, (current_price, now, pnl, pnl_pct, now, trade['id']))
                        conn.commit()
                        
                        log(f"[TARGET HIT] {symbol} @ {current_price:.2f} | PnL: {pnl:.2f} ({pnl_pct:.2f}%)")
                        
        except Exception as e:
            log(f"Error updating trades: {e}")
    
    def run(self):
        """Main application loop"""
        log("=" * 70)
        log("CRYPTO TRADING APP - Delta India Exchange")
        log("Market Open: 00:00 UTC (5:30 AM IST) | 24/7 Trading")
        log("=" * 70)
        
        if not self.initialize():
            log("Initialization failed!")
            return
        
        self.running = True
        
        # Start WebSocket in background thread
        log("Starting WebSocket for real-time data...")
        self.ws = DeltaWebSocket(self.auth, self.symbols)
        self.ws.add_callback(self.on_market_data)
        
        ws_thread = threading.Thread(target=self.ws.connect, daemon=True)
        ws_thread.start()
        
        # Wait for WebSocket to connect
        time.sleep(3)
        
        # Fetch initial data
        log("Fetching first closes (00:00 UTC / 5:30 AM IST)...")
        self.fetch_first_closes()
        
        # Main loop
        last_snapshot = time.time()
        last_paper_cycle = time.time()
        last_trade_update = time.time()
        last_price_sim = time.time()
        
        log("Main loop started - Running 24/7")
        log("SIMULATION MODE: Prices are simulated for testing")
        
        try:
            while self.running:
                time.sleep(1)
                
                now = time.time()
                
                # Simulate prices every 2 seconds
                if now - last_price_sim >= 2:
                    self.simulate_prices()
                    last_price_sim = now
                
                # Generate snapshot every 5 seconds
                if now - last_snapshot >= 5:
                    self.generate_snapshot()
                    last_snapshot = now
                
                # Paper trading cycle every 3 seconds
                if now - last_paper_cycle >= 3:
                    self.run_paper_cycle()
                    last_paper_cycle = now
                
                # Update open trades every 2 seconds
                if now - last_trade_update >= 2:
                    self.update_open_trades()
                    last_trade_update = now
                
        except KeyboardInterrupt:
            log("Shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the application"""
        self.running = False
        if self.ws:
            self.ws.stop()
        self._flush_ticks()
        log("Crypto App stopped")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    app = CryptoApp()
    app.run()


if __name__ == "__main__":
    main()
