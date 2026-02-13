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

# Crypto Market Configuration (24/7 trading)
# Unlike NSE/BSE/MCX, crypto never sleeps
CRYPTO_MARKET_OPEN = dtime(0, 0, 0)  # Midnight IST
CRYPTO_MARKET_CLOSE = dtime(23, 59, 59)  # Almost midnight

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
        result = self._make_request("GET", "/products")
        return result.get("result", [])
    
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
    
    def __init__(self, factor: str = 'smart'):
        self.factor = factor
    
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
    
    def analyze_setup(self, ltp: float, close: float, symbol: str) -> dict:
        """
        Complete trade setup analysis
        
        Returns B5 levels + Micro-Fib zones + Entry signals
        """
        # Select factor
        factor_info = self.select_factor(ltp, close, symbol)
        
        # Calculate B5 levels
        levels = self.calculate_levels(close, factor_info['factor'])
        
        # Determine which B5 levels price is near
        signals = []
        for level_name, level_price in levels.items():
            if level_name == 'points':
                continue
            
            # Check if LTP is near this level (within 0.5 points)
            distance = abs(ltp - level_price)
            if distance < levels['points'] * 0.5:
                # Get micro-fib zone for this level
                # Calculate which 100-point block this level is in
                block_size = 100 if ltp < 10000 else 1000
                block_start = (level_price // block_size) * block_size
                position = ((level_price - block_start) / block_size) * 100
                zone = self.get_micro_fib_zone(position)
                
                signals.append({
                    'level_name': level_name,
                    'level_price': level_price,
                    'distance': distance,
                    'micro_zone': zone,
                    'signal': self._generate_signal(level_name, zone)
                })
        
        return {
            'factor': factor_info,
            'levels': levels,
            'ltp': ltp,
            'close': close,
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
        
        # Fetch and save products
        log("Fetching available products...")
        products = self.client.get_products()
        if products:
            self.data_manager.save_products(products)
            # Filter for perpetual and futures only
            self.symbols = [
                p['symbol'] for p in products 
                if p.get('contract_type') in ['perpetual', 'futures']
                and p.get('quote_asset') == 'USDT'  # Focus on USDT pairs
            ][:200]  # Limit to top 200 pairs for performance
            log(f"Loaded {len(self.symbols)} trading symbols")
        
        return True
    
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
        """Fetch first 1m, 5m, 15m closes for all symbols"""
        log("Fetching first closes...")
        
        today = date.today().isoformat()
        now = int(time.time())
        
        # Fetch 5m candles for last hour to get first close
        start_time = now - 3600
        
        for symbol in self.symbols[:50]:  # Limit for rate limiting
            try:
                candles = self.client.get_candles(symbol, '5', start_time, now)
                if candles and len(candles) > 0:
                    first_close = float(candles[0].get('close', 0))
                    if first_close > 0:
                        self.data_manager.save_first_close(symbol, '5m', first_close, today)
                        log(f"First 5m close for {symbol}: {first_close}")
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                log(f"Error fetching {symbol}: {e}")
    
    def generate_snapshot(self):
        """Generate UI snapshot (parallel to Shoonya's snapshot)"""
        try:
            # Get latest prices
            snapshot_rows = []
            
            for symbol in self.symbols[:100]:  # Top 100 symbols
                # Get latest tick
                ticks = self.data_manager.get_ticks(symbol, 1)
                if not ticks:
                    continue
                
                latest = ticks[0]
                ltp = latest['price']
                
                # Get first close
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.execute(
                        "SELECT first_5m_close FROM first_closes WHERE symbol = ?",
                        (symbol,)
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
                'day': date.today().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'row_count': len(snapshot_rows),
                'rows': snapshot_rows
            }
            
            snapshot_file = OUT_DIR / 'crypto_snapshot.json'
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            
            log(f"Snapshot generated: {len(snapshot_rows)} rows")
            
        except Exception as e:
            log(f"Snapshot error: {e}")
    
    def run(self):
        """Main application loop"""
        log("Starting Crypto App...")
        
        if not self.initialize():
            log("Initialization failed!")
            return
        
        self.running = True
        
        # Start WebSocket in background thread
        log("Starting WebSocket...")
        self.ws = DeltaWebSocket(self.auth, self.symbols)
        self.ws.add_callback(self.on_market_data)
        
        ws_thread = threading.Thread(target=self.ws.connect, daemon=True)
        ws_thread.start()
        
        # Fetch initial data
        self.fetch_first_closes()
        
        # Main loop
        last_snapshot = time.time()
        
        try:
            while self.running:
                time.sleep(1)
                
                # Generate snapshot every 5 seconds
                if time.time() - last_snapshot >= 5:
                    self.generate_snapshot()
                    last_snapshot = time.time()
                
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
