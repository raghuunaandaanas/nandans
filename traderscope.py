#!/usr/bin/env python3
"""
================================================================================
TRADERSCOPE - Universal Micro-Fibonacci Analysis Engine
================================================================================
REPLICATED FROM: User's price action knowledge
PURPOSE: Multi-digit level analysis for all instruments (Crypto, Stocks, etc.)

GIT TRACKING:
- Created: 2026-02-13
- Author: AI Assistant
- Feature: Traderscope Microscope - Multi-digit price analysis
- Status: New module for crypto app

UNIVERSAL PRINCIPLE:
All prices move in fractal patterns across digit magnitudes:
- Digit 6 (Units): ×1 - Micro scalping
- Digit 5 (Tens): ×10 - Standard intraday
- Digit 4 (Hundreds): ×100 - Swing trading
- Digit 3 (Thousands): ×1000 - Position trading
- Digit 2 (Ten-thousands): ×10000 - Long term

Each 100-point block contains:
- 0-11.8: Major support (time-based)
- 11.8-22: Early support
- 22-28: Floor (test 3x then trend)
- 28-35: Support test → confirmation
- 35-38: Confirmation zone
- 38-45: 1st retracement (caution)
- 45-50: Rejection zone (avoid entry)
- 50: Midpoint (trend confirmation)
- 50-61.8: Trend building
- 61.8: Major fib target
- 61.8-78: Acceleration zone
- 78: Fast trend starts
- 78-88: High momentum
- 88: Decision point (continue/reverse)
- 88-95: Late trend (tighten stops)
- 95-100: Major rejection zone
- 100: Next block

VOLATILITY-BASED DIGIT SELECTION:
- Low volatility → Digit 6 (small moves)
- Medium volatility → Digit 5
- High volatility → Digit 4
- Extreme volatility → Digit 3
================================================================================
"""

import json
import sqlite3
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import statistics


# =============================================================================
# UNIVERSAL MICRO-FIB ZONES (Same for ALL instruments worldwide)
# =============================================================================

MICRO_ZONES = {
    # Zone start: {name, type, priority, description, action}
    0.0: {
        'name': 'start',
        'type': 'support',
        'priority': 1,
        'description': 'Block start / major support',
        'action': 'WATCH_FOR_BOUNCE',
        'risk': 'LOW'
    },
    11.8: {
        'name': 'support_time',
        'type': 'support',
        'priority': 2,
        'description': 'Major time-based support',
        'action': 'BOUNCE_EXPECTED',
        'risk': 'LOW'
    },
    22.0: {
        'name': 'floor',
        'type': 'support',
        'priority': 3,
        'description': 'Floor level - must hold',
        'action': 'CRITICAL_SUPPORT',
        'risk': 'MEDIUM',
        'special': 'TEST_3X_RULE'  # Test 3 times then trend to 35
    },
    28.0: {
        'name': 'support_test',
        'type': 'support',
        'priority': 4,
        'description': 'Support test zone',
        'action': 'WATCH_3_TESTS',
        'risk': 'MEDIUM',
        'special': '3_TESTS_TO_35'
    },
    35.0: {
        'name': 'confirmation',
        'type': 'neutral',
        'priority': 5,
        'description': 'Confirmation level',
        'action': 'CONFIRMATION',
        'risk': 'MEDIUM'
    },
    38.2: {
        'name': 'retracement_1',
        'type': 'resistance',
        'priority': 6,
        'description': '1st retracement zone',
        'action': 'CAUTION',
        'risk': 'MEDIUM'
    },
    45.0: {
        'name': 'rejection',
        'type': 'resistance',
        'priority': 7,
        'description': 'Rejection zone - avoid entry',
        'action': 'AVOID_ENTRY',
        'risk': 'HIGH',
        'special': 'EXIT_ZONE'
    },
    50.0: {
        'name': 'midpoint',
        'type': 'neutral',
        'priority': 8,
        'description': 'Midpoint - trend confirmation',
        'action': 'ABOVE_50_BULLISH',
        'risk': 'MEDIUM'
    },
    61.8: {
        'name': 'fib_major',
        'type': 'target',
        'priority': 9,
        'description': 'Major fibonacci target',
        'action': 'TARGET_REACHED',
        'risk': 'LOW'
    },
    78.0: {
        'name': 'trend_fast',
        'type': 'acceleration',
        'priority': 10,
        'description': 'Trend acceleration zone',
        'action': 'ADD_POSITION',
        'risk': 'LOW',
        'special': 'FAST_MOVE'
    },
    88.0: {
        'name': 'decision',
        'type': 'critical',
        'priority': 11,
        'description': 'Decision point - continue or reverse',
        'action': 'WATCH_CLOSELY',
        'risk': 'HIGH',
        'special': 'TREND_DECISION'
    },
    95.0: {
        'name': 'rejection_major',
        'type': 'resistance',
        'priority': 12,
        'description': 'Major rejection zone',
        'action': 'EXIT_IMMEDIATELY',
        'risk': 'VERY_HIGH',
        'special': 'MAJOR_REJECT'
    },
    100.0: {
        'name': 'next_block',
        'type': 'target',
        'priority': 13,
        'description': 'Next block start',
        'action': 'BLOCK_COMPLETE',
        'risk': 'LOW'
    }
}


# =============================================================================
# SPECIAL RULES (User's proprietary knowledge)
# =============================================================================

SPECIAL_RULES = {
    '28_ZONE': {
        'description': 'Price tests 28 three times before moving to 35',
        'trigger': 'TOUCH_COUNT >= 3',
        'action': 'EXPECT_MOVE_TO_35',
        'confidence': 0.85
    },
    '22_SUPPORT': {
        'description': 'Must hold above 22 for trend continuation',
        'trigger': 'PRICE_BELOW_22',
        'action': 'STOP_LOSS',
        'confidence': 0.90
    },
    '50_CONFIRMATION': {
        'description': 'Close above 50 confirms bullish trend',
        'trigger': 'CLOSE_ABOVE_50',
        'action': 'ENTER_LONG',
        'confidence': 0.80
    },
    '78_ACCELERATION': {
        'description': 'Fast trend starts at 78',
        'trigger': 'PRICE_ABOVE_78',
        'action': 'ADD_POSITION',
        'confidence': 0.75
    },
    '88_DECISION': {
        'description': 'Price either continues to 95+ or reverses to 78',
        'trigger': 'PRICE_AT_88',
        'action': 'TIGHTEN_STOPS',
        'confidence': 0.70
    },
    '95_REJECTION': {
        'description': 'Major rejection - exit or reverse',
        'trigger': 'PRICE_AT_95',
        'action': 'EXIT_OR_REVERSE',
        'confidence': 0.85
    }
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DigitAnalysis:
    """Analysis for a single digit level"""
    digit: int                    # 6=units, 5=tens, etc.
    magnitude: float              # 1, 10, 100, 1000, 10000
    block_start: float            # Start of current 100-point block
    block_end: float              # End of block
    position: float               # Position within block (0-100)
    zone: Dict                    # Current zone info
    next_zone: Dict               # Next zone
    prev_zone: Dict               # Previous zone
    touches: int                  # Number of times tested
    is_active: bool               # Is this digit level active


@dataclass
class RangeShift:
    """Detected range shift event"""
    timestamp: str
    symbol: str
    digit: int
    direction: str                # 'UP' or 'DOWN'
    from_block: float
    to_block: float
    magnitude: float
    price: float


@dataclass
class PriceObservation:
    """Recorded price observation for ML learning"""
    timestamp: str
    symbol: str
    ltp: float
    digit: int
    block_start: float
    position: float
    zone_name: str
    b5_level: str                 # BU1, BU2, etc.
    volume: float
    entry_signal: str
    outcome: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    exit_time: Optional[str] = None


# =============================================================================
# TRADERSCOPE ENGINE
# =============================================================================

class TraderscopeEngine:
    """
    Universal price analysis engine
    
    Works for: Crypto, Stocks, Options, Forex, Commodities - ANY instrument
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.touches = defaultdict(lambda: defaultdict(int))  # symbol -> zone -> count
        self.block_history = defaultdict(list)  # symbol -> list of blocks visited
        self.recent_shifts = []  # List of RangeShift
        
    # -------------------------------------------------------------------------
    # Core Calculations
    # -------------------------------------------------------------------------
    
    def calculate_digit_analysis(self, ltp: float, digit: int) -> DigitAnalysis:
        """
        Calculate micro-fib analysis for a specific digit level
        
        Args:
            ltp: Current price
            digit: 6=units, 5=tens, 4=hundreds, 3=thousands, 2=ten-thousands
        """
        magnitude = 10 ** (6 - digit)  # digit 6 = 1, digit 5 = 10, etc.
        
        # Calculate block
        block_start = (ltp // magnitude) * magnitude
        block_end = block_start + magnitude
        
        # Position within block (0-100)
        position = ((ltp - block_start) / magnitude) * 100
        
        # Get current zone
        zone = self._get_zone(position)
        next_zone = self._get_next_zone(position)
        prev_zone = self._get_prev_zone(position)
        
        # Count touches
        zone_key = f"{digit}_{zone['name']}"
        self.touches[ltp][zone_key] += 1
        
        return DigitAnalysis(
            digit=digit,
            magnitude=magnitude,
            block_start=block_start,
            block_end=block_end,
            position=position,
            zone=zone,
            next_zone=next_zone,
            prev_zone=prev_zone,
            touches=self.touches[ltp][zone_key],
            is_active=True
        )
    
    def analyze_all_digits(self, ltp: float, min_digit: int = 2, max_digit: int = 6) -> List[DigitAnalysis]:
        """
        Analyze price across all digit levels
        
        Returns list from smallest (units) to largest (ten-thousands)
        """
        analyses = []
        for digit in range(max_digit, min_digit - 1, -1):
            analysis = self.calculate_digit_analysis(ltp, digit)
            analyses.append(analysis)
        return analyses
    
    def select_active_digit(self, ltp: float, volatility: float = None, atr: float = None) -> int:
        """
        Select which digit level to trade based on volatility
        
        Volatility-based selection:
        - Very low: Digit 6 (micro moves)
        - Low: Digit 5 (normal moves)
        - Medium: Digit 4 (larger moves)
        - High: Digit 3 (major moves)
        - Extreme: Digit 2 (structural moves)
        """
        if volatility is None:
            # Auto-detect based on price magnitude
            if ltp < 100:
                return 6  # Units for penny stocks/low price crypto
            elif ltp < 1000:
                return 5  # Tens for normal prices
            elif ltp < 10000:
                return 4  # Hundreds for larger prices
            elif ltp < 100000:
                return 3  # Thousands for BTC, etc.
            else:
                return 2  # Ten-thousands for extreme prices
        
        # Volatility-based selection
        if volatility < 0.5:
            return 6
        elif volatility < 2.0:
            return 5
        elif volatility < 5.0:
            return 4
        elif volatility < 10.0:
            return 3
        else:
            return 2
    
    # -------------------------------------------------------------------------
    # Zone Detection
    # -------------------------------------------------------------------------
    
    def _get_zone(self, position: float) -> Dict:
        """Get zone information for position (0-100)"""
        zone_keys = sorted(MICRO_ZONES.keys())
        
        for i in range(len(zone_keys) - 1):
            lower = zone_keys[i]
            upper = zone_keys[i + 1]
            if lower <= position < upper:
                zone = MICRO_ZONES[lower].copy()
                zone['lower'] = lower
                zone['upper'] = upper
                zone['progress'] = (position - lower) / (upper - lower)
                return zone
        
        # Beyond 100
        return {
            'name': 'beyond',
            'type': 'unknown',
            'lower': 100,
            'upper': 100,
            'progress': 0,
            'priority': 99
        }
    
    def _get_next_zone(self, position: float) -> Dict:
        """Get next zone"""
        zone_keys = sorted(MICRO_ZONES.keys())
        current = self._get_zone(position)
        current_lower = current['lower']
        
        for i, key in enumerate(zone_keys):
            if key == current_lower and i + 1 < len(zone_keys):
                next_key = zone_keys[i + 1]
                zone = MICRO_ZONES[next_key].copy()
                zone['lower'] = next_key
                return zone
        
        return {'name': 'end', 'type': 'unknown'}
    
    def _get_prev_zone(self, position: float) -> Dict:
        """Get previous zone"""
        zone_keys = sorted(MICRO_ZONES.keys())
        current = self._get_zone(position)
        current_lower = current['lower']
        
        for i, key in enumerate(zone_keys):
            if key == current_lower and i > 0:
                prev_key = zone_keys[i - 1]
                zone = MICRO_ZONES[prev_key].copy()
                zone['lower'] = prev_key
                return zone
        
        return {'name': 'start', 'type': 'unknown'}
    
    # -------------------------------------------------------------------------
    # Range Shift Detection
    # -------------------------------------------------------------------------
    
    def detect_range_shift(self, symbol: str, prev_ltp: float, curr_ltp: float, 
                          prev_analysis: List[DigitAnalysis], 
                          curr_analysis: List[DigitAnalysis]) -> List[RangeShift]:
        """
        Detect when price shifts to new block at any digit level
        
        This is KEY for capturing explosive moves (gamma squeezes)
        """
        shifts = []
        timestamp = datetime.now().isoformat()
        
        for prev, curr in zip(prev_analysis, curr_analysis):
            if prev.block_start != curr.block_start:
                direction = 'UP' if curr.block_start > prev.block_start else 'DOWN'
                
                shift = RangeShift(
                    timestamp=timestamp,
                    symbol=symbol,
                    digit=curr.digit,
                    direction=direction,
                    from_block=prev.block_start,
                    to_block=curr.block_start,
                    magnitude=curr.magnitude,
                    price=curr_ltp
                )
                
                shifts.append(shift)
                self.recent_shifts.append(shift)
                
                # Keep only recent shifts
                if len(self.recent_shifts) > 1000:
                    self.recent_shifts = self.recent_shifts[-500:]
        
        return shifts
    
    def get_recent_shifts(self, symbol: str = None, digit: int = None, limit: int = 50) -> List[RangeShift]:
        """Get recent range shifts with optional filtering"""
        shifts = self.recent_shifts
        
        if symbol:
            shifts = [s for s in shifts if s.symbol == symbol]
        if digit:
            shifts = [s for s in shifts if s.digit == digit]
        
        return shifts[-limit:]
    
    # -------------------------------------------------------------------------
    # Signal Generation
    # -------------------------------------------------------------------------
    
    def generate_signal(self, analysis: DigitAnalysis, b5_level: str = None) -> Dict:
        """
        Generate trading signal based on digit analysis and B5 level
        """
        zone = analysis.zone
        position = analysis.position
        touches = analysis.touches
        
        signal = {
            'action': zone.get('action', 'WATCH'),
            'strength': 'NEUTRAL',
            'confidence': 0.5,
            'zone': zone['name'],
            'reason': zone.get('description', ''),
            'special_rules': []
        }
        
        # Apply special rules
        if zone['name'] == 'support_test' and touches >= 3:
            signal['special_rules'].append('28_3X_RULE')
            signal['action'] = 'EXPECT_MOVE_TO_35'
            signal['confidence'] = SPECIAL_RULES['28_ZONE']['confidence']
        
        if zone['name'] == 'rejection' or zone['name'] == 'rejection_major':
            signal['strength'] = 'AVOID'
            signal['confidence'] = 0.85
        
        if zone['name'] == 'trend_fast':
            signal['strength'] = 'STRONG'
            signal['action'] = 'ADD_POSITION'
        
        if zone['name'] == 'decision':
            signal['strength'] = 'CAUTION'
            signal['action'] = 'TIGHTEN_STOPS'
        
        # Combine with B5 level
        if b5_level:
            b5_score = self._b5_level_score(b5_level)
            signal['b5_boost'] = b5_score
            signal['confidence'] = min(0.95, signal['confidence'] + b5_score * 0.1)
        
        return signal
    
    def _b5_level_score(self, level: str) -> int:
        """Score B5 level importance"""
        scores = {
            'bu1': 1, 'bu2': 2, 'bu3': 3, 'bu4': 4, 'bu5': 5,
            'be1': 1, 'be2': 2, 'be3': 3, 'be4': 4, 'be5': 5
        }
        return scores.get(level.lower(), 0)
    
    # -------------------------------------------------------------------------
    # Gamma Move Detection
    # -------------------------------------------------------------------------
    
    def detect_gamma_move(self, symbol: str, price_history: List[float], 
                         digit_analysis: List[DigitAnalysis]) -> Optional[Dict]:
        """
        Detect explosive gamma moves using multi-digit confluence
        
        Gamma squeeze conditions:
        1. Multiple digits shifting simultaneously
        2. Price crossing 78-zone on multiple levels
        3. Volume spike (checked externally)
        4. Consecutive block breaks
        """
        if len(price_history) < 5:
            return None
        
        # Check for rapid price increase
        price_change = (price_history[-1] - price_history[0]) / price_history[0] * 100
        
        # Check if multiple digits are in acceleration zone
        accel_digits = [d for d in digit_analysis if d.zone['name'] == 'trend_fast']
        
        # Check for consecutive range shifts
        recent_shifts = self.get_recent_shifts(symbol=symbol, limit=10)
        consecutive_shifts = len([s for s in recent_shifts if s.direction == 'UP'])
        
        gamma_score = 0
        signals = []
        
        if price_change > 2:  # 2% move
            gamma_score += 1
            signals.append('price_spike')
        
        if len(accel_digits) >= 2:  # Multiple digits in 78-zone
            gamma_score += 2
            signals.append('multi_digit_accel')
        
        if consecutive_shifts >= 3:  # 3+ consecutive up shifts
            gamma_score += 2
            signals.append('consecutive_shifts')
        
        if gamma_score >= 3:
            return {
                'detected': True,
                'score': gamma_score,
                'signals': signals,
                'price_change': price_change,
                'accel_digits': len(accel_digits),
                'action': 'ADD_POSITION',
                'target': 'NEXT_BLOCK',
                'urgency': 'HIGH'
            }
        
        return None
    
    # -------------------------------------------------------------------------
    # ML Learning Interface
    # -------------------------------------------------------------------------
    
    def record_observation(self, observation: PriceObservation):
        """Record price observation for ML learning"""
        if not self.db_path:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO traderscope_observations 
                    (timestamp, symbol, ltp, digit, block_start, position, 
                     zone_name, b5_level, volume, entry_signal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    observation.timestamp, observation.symbol, observation.ltp,
                    observation.digit, observation.block_start, observation.position,
                    observation.zone_name, observation.b5_level, observation.volume,
                    observation.entry_signal
                ))
                conn.commit()
        except Exception as e:
            print(f"Error recording observation: {e}")
    
    def update_outcome(self, symbol: str, entry_time: str, outcome: str, 
                      exit_price: float, pnl: float):
        """Update observation with outcome"""
        if not self.db_path:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE traderscope_observations 
                    SET outcome = ?, exit_price = ?, pnl = ?, exit_time = ?
                    WHERE symbol = ? AND timestamp = ?
                """, (outcome, exit_price, pnl, datetime.now().isoformat(), 
                      symbol, entry_time))
                conn.commit()
        except Exception as e:
            print(f"Error updating outcome: {e}")
    
    def get_zone_statistics(self, symbol: str, zone_name: str, b5_level: str = None) -> Dict:
        """Get ML statistics for a specific zone + B5 combination"""
        if not self.db_path:
            return {'total': 0, 'success': 0, 'avg_pnl': 0}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) as success,
                           AVG(pnl) as avg_pnl
                    FROM traderscope_observations
                    WHERE symbol = ? AND zone_name = ?
                """
                params = [symbol, zone_name]
                
                if b5_level:
                    query += " AND b5_level = ?"
                    params.append(b5_level)
                
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                
                return {
                    'total': row[0] or 0,
                    'success': row[1] or 0,
                    'avg_pnl': row[2] or 0,
                    'success_rate': (row[1] / row[0] * 100) if row[0] else 0
                }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {'total': 0, 'success': 0, 'avg_pnl': 0}


# =============================================================================
# DATABASE SCHEMA FOR ML
# =============================================================================

TRADERSCOPE_DB_SCHEMA = """
-- Price observations for ML learning
CREATE TABLE IF NOT EXISTS traderscope_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ltp REAL NOT NULL,
    digit INTEGER NOT NULL,
    block_start REAL NOT NULL,
    position REAL NOT NULL,
    zone_name TEXT NOT NULL,
    b5_level TEXT,
    volume REAL,
    entry_signal TEXT,
    outcome TEXT,  -- SUCCESS, FAILURE, PARTIAL
    exit_price REAL,
    pnl REAL,
    exit_time TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Range shifts history
CREATE TABLE IF NOT EXISTS range_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    digit INTEGER NOT NULL,
    direction TEXT NOT NULL,
    from_block REAL NOT NULL,
    to_block REAL NOT NULL,
    magnitude REAL NOT NULL,
    price REAL NOT NULL
);

-- Zone touch counts
CREATE TABLE IF NOT EXISTS zone_touches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    digit INTEGER NOT NULL,
    zone_name TEXT NOT NULL,
    touch_count INTEGER DEFAULT 0,
    last_touch TEXT,
    UNIQUE(symbol, digit, zone_name)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_obs_symbol ON traderscope_observations(symbol);
CREATE INDEX IF NOT EXISTS idx_obs_zone ON traderscope_observations(zone_name);
CREATE INDEX IF NOT EXISTS idx_obs_b5 ON traderscope_observations(b5_level);
CREATE INDEX IF NOT EXISTS idx_shifts_symbol ON range_shifts(symbol);
"""


def init_traderscope_db(db_path: str):
    """Initialize Traderscope database"""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(TRADERSCOPE_DB_SCHEMA)
        conn.commit()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: Analyze BTC price
    engine = TraderscopeEngine()
    
    ltp = 67456.80
    
    # Analyze all digit levels
    analyses = engine.analyze_all_digits(ltp)
    
    print(f"\n{'='*60}")
    print(f"TRADERSCOPE ANALYSIS for BTC @ ${ltp:,.2f}")
    print(f"{'='*60}")
    
    for analysis in analyses:
        print(f"\nDigit {analysis.digit} (×{analysis.magnitude:,.0f}):")
        print(f"  Block: {analysis.block_start:,.2f} - {analysis.block_end:,.2f}")
        print(f"  Position: {analysis.position:.2f}%")
        print(f"  Zone: {analysis.zone['name']} ({analysis.zone['type']})")
        print(f"  Action: {analysis.zone.get('action', 'WATCH')}")
        
        # Generate signal
        signal = engine.generate_signal(analysis, 'bu3')
        print(f"  Signal: {signal['action']} (confidence: {signal['confidence']:.0%})")
    
    # Select best digit for trading
    selected = engine.select_active_digit(ltp, volatility=3.5)
    print(f"\n{'='*60}")
    print(f"RECOMMENDED DIGIT: {selected} for current volatility")
    print(f"{'='*60}")
