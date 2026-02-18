# Design Document

## Overview

The B5 Factor / Traderscope trading system is a high-frequency trading platform that uses mathematical level calculations based on the master number 0.2611 to identify precise entry and exit points. The system operates on the principle that markets move in numbers and levels, not indicators.

The architecture consists of four main Python modules totaling 3000-5000 lines of optimized code, six SQLite databases for data persistence, and a web-based UI for real-time monitoring. The system integrates with Delta Exchange for cryptocurrency trading and Shoonya API for Indian markets (NSE/BSE/MCX).

Key design principles:
- **Numbers-only approach**: No technical indicators, only B5 Factor level calculations
- **AUTO SENSE intelligence**: ML-powered decision making for factor selection, entry/exit timing
- **Zero manual intervention**: Fully automated trading with 24/7 operation
- **Multi-timeframe coordination**: 1m, 5m, 15m timeframes working together
- **Profit riding**: Tiny stop losses with trailing stops to maximize gains
- **Three trading modes**: Soft (conservative), Smooth (balanced), Aggressive (high-frequency)

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Web UI (index.html)                  │
│  Real-time visualization, level display, position monitoring │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────┴────────────────────────────────────────┐
│                      main.py (Core System)                   │
│  - Trading engine                                            │
│  - AUTO SENSE coordinator                                    │
│  - Level calculator                                          │
│  - Signal generator                                          │
│  - Position manager                                          │
│  - Risk manager                                              │
└──────┬──────────────┬──────────────┬────────────────────────┘
       │              │              │
┌──────┴──────┐ ┌────┴─────┐ ┌──────┴──────┐
│ api_integrations.py │ ml_engine.py │ utils.py    │
│ - Delta API  │ │ - Pattern │ │ - Helpers   │
│ - Shoonya API│ │   learning│ │ - Validators│
│ - Order mgmt │ │ - AUTO    │ │ - Formatters│
│ - Data fetch │ │   SENSE   │ │ - Logging   │
└──────┬──────┘ └────┬─────┘ └─────────────┘
       │              │
┌──────┴──────────────┴──────────────────────────────────────┐
│                    SQLite Databases                          │
│  trades.db | patterns.db | performance.db                   │
│  levels.db | positions.db | config.db                       │
└─────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

**main.py** (1500-2000 lines)
- Core trading engine orchestration
- Level calculation using B5 Factor
- Entry/exit signal generation
- Position and order management
- Risk management enforcement
- HTTP server for UI
- Real-time data streaming

**api_integrations.py** (800-1200 lines)
- Delta Exchange API client (authentication, market data, orders)
- Shoonya API client (authentication, market data, orders)
- WebSocket connections for real-time data
- Order placement and modification
- Error handling and retry logic
- Rate limit management

**ml_engine.py** (500-800 lines)
- Pattern recognition and learning
- AUTO SENSE decision making
- Factor selection optimization
- Entry/exit timing prediction
- Spike detection classification
- Model training and retraining
- Performance tracking

**utils.py** (200-400 lines)
- Number formatting and validation
- Time zone conversions (IST, UTC)
- Database helpers
- Logging configuration
- Configuration management
- Report generation helpers

## Components and Interfaces

### Level Calculator

The Level Calculator is the heart of the B5 Factor system. It calculates BU (Bullish) and BE (Bearish) levels based on the first candle close price.

```python
class LevelCalculator:
    def calculate_levels(base_price: float, timeframe: str) -> dict:
        """
        Calculate BU1-BU5 and BE1-BE5 levels
        
        Args:
            base_price: First candle close price
            timeframe: '1m', '5m', or '15m'
            
        Returns:
            {
                'base': float,
                'factor': float,
                'points': float,
                'bu1': float, 'bu2': float, 'bu3': float, 'bu4': float, 'bu5': float,
                'be1': float, 'be2': float, 'be3': float, 'be4': float, 'be5': float
            }
        """
        # Determine factor based on price range
        if base_price < 1000:
            factor = 0.2611  # 26.11%
        elif base_price < 10000:
            factor = 0.02611  # 2.61%
        else:
            factor = 0.002611  # 0.2611%
        
        points = base_price * factor
        
        return {
            'base': base_price,
            'factor': factor,
            'points': points,
            'bu1': base_price + points * 1,
            'bu2': base_price + points * 2,
            'bu3': base_price + points * 3,
            'bu4': base_price + points * 4,
            'bu5': base_price + points * 5,
            'be1': base_price - points * 1,
            'be2': base_price - points * 2,
            'be3': base_price - points * 3,
            'be4': base_price - points * 4,
            'be5': base_price - points * 5
        }
```

### Signal Generator

The Signal Generator monitors price movements and generates entry/exit signals based on level crosses.

```python
class SignalGenerator:
    def check_entry_signal(current_price: float, levels: dict, mode: str) -> dict:
        """
        Check for entry signals
        
        Args:
            current_price: Current market price
            levels: Calculated BU/BE levels
            mode: 'soft', 'smooth', or 'aggressive'
            
        Returns:
            {
                'signal': 'buy' | 'sell' | None,
                'level': 'BU1' | 'BE1' | None,
                'confidence': float (0-1),
                'wait_for_close': bool
            }
        """
        # Bullish signal: price crosses above BU1
        if current_price > levels['bu1']:
            wait_for_close = mode == 'soft' or (mode == 'smooth' and confidence < 0.7)
            return {
                'signal': 'buy',
                'level': 'BU1',
                'confidence': calculate_confidence(current_price, levels),
                'wait_for_close': wait_for_close
            }
        
        # Bearish signal: price crosses below BE1
        if current_price < levels['be1']:
            wait_for_close = mode == 'soft' or (mode == 'smooth' and confidence < 0.7)
            return {
                'signal': 'sell',
                'level': 'BE1',
                'confidence': calculate_confidence(current_price, levels),
                'wait_for_close': wait_for_close
            }
        
        return {'signal': None, 'level': None, 'confidence': 0, 'wait_for_close': False}
    
    def check_exit_signal(current_price: float, position: dict, levels: dict) -> dict:
        """
        Check for exit signals
        
        Returns:
            {
                'action': 'exit_partial' | 'exit_full' | 'reverse' | None,
                'level': 'BU2' | 'BU3' | 'BU4' | 'BU5' | None,
                'percentage': float (0-1)
            }
        """
        if position['direction'] == 'long':
            if current_price >= levels['bu5']:
                return {'action': 'exit_full', 'level': 'BU5', 'percentage': 1.0}
            elif current_price >= levels['bu4']:
                return {'action': 'exit_partial', 'level': 'BU4', 'percentage': 0.25}
            elif current_price >= levels['bu3']:
                return {'action': 'exit_partial', 'level': 'BU3', 'percentage': 0.25}
            elif current_price >= levels['bu2']:
                return {'action': 'exit_partial', 'level': 'BU2', 'percentage': 0.25}
        
        return {'action': None, 'level': None, 'percentage': 0}
```

### Position Manager

The Position Manager handles position sizing, pyramiding, and stop loss management.

```python
class PositionManager:
    def calculate_position_size(account_capital: float, risk_percent: float, 
                               stop_loss_distance: float) -> float:
        """
        Calculate position size based on risk parameters
        
        Formula: position_size = (account_capital * risk_percent) / stop_loss_distance
        """
        return (account_capital * risk_percent) / stop_loss_distance
    
    def should_pyramid(position: dict, current_price: float, levels: dict) -> dict:
        """
        Determine if pyramiding should occur
        
        Returns:
            {
                'should_pyramid': bool,
                'size_multiplier': float,
                'reason': str
            }
        """
        # Check if price retraced to a level
        if position['direction'] == 'long':
            for level_name in ['bu1', 'bu2', 'bu3', 'bu4']:
                level_price = levels[level_name]
                if abs(current_price - level_price) < levels['points'] * 0.1:
                    # Price is near a level, consider pyramiding
                    current_size = position['total_size']
                    max_size = position['initial_size'] * 100
                    
                    if current_size < max_size:
                        multiplier = min(2.0, max_size / current_size)
                        return {
                            'should_pyramid': True,
                            'size_multiplier': multiplier,
                            'reason': f'Retracement to {level_name.upper()}'
                        }
        
        return {'should_pyramid': False, 'size_multiplier': 0, 'reason': ''}
    
    def calculate_stop_loss(entry_price: float, levels: dict, direction: str) -> float:
        """
        Calculate stop loss at 50% between base and BU1/BE1
        """
        if direction == 'long':
            return levels['base'] + (levels['points'] * 0.5)
        else:
            return levels['base'] - (levels['points'] * 0.5)
```

### AUTO SENSE Engine

The AUTO SENSE engine uses machine learning to optimize trading decisions.

```python
class AutoSenseEngine:
    def select_optimal_factor(base_price: float, volatility: float, 
                             historical_performance: dict) -> float:
        """
        Use ML to select optimal factor variation
        
        Returns: 0.002611, 0.02611, or 0.2611
        """
        # Feature vector: [base_price, volatility, time_of_day, day_of_week]
        features = extract_features(base_price, volatility)
        
        # Predict best factor using trained model
        predicted_factor = ml_model.predict(features)
        
        return predicted_factor
    
    def predict_entry_timing(price_action: list, volume: list, levels: dict) -> str:
        """
        Predict whether to enter on cross or wait for close
        
        Returns: 'immediate' or 'wait_for_close'
        """
        # Analyze momentum, volume, and historical patterns
        momentum = calculate_momentum(price_action)
        volume_strength = analyze_volume(volume)
        pattern_match = find_similar_patterns(price_action, historical_patterns)
        
        if momentum > 0.7 and volume_strength > 0.6:
            return 'immediate'
        else:
            return 'wait_for_close'
    
    def predict_exit_percentages(current_level: str, price_behavior: dict) -> float:
        """
        Predict optimal exit percentage at each level
        
        Returns: percentage to exit (0.0 to 1.0)
        """
        # Analyze historical rejection rate at this level
        rejection_rate = price_behavior.get(f'{current_level}_rejection_rate', 0.5)
        
        # Higher rejection rate = exit more
        if rejection_rate > 0.7:
            return 0.4  # Exit 40%
        elif rejection_rate > 0.5:
            return 0.25  # Exit 25%
        else:
            return 0.15  # Exit 15%
```

### Spike Detector

The Spike Detector identifies real vs fake price spikes using volume and price action analysis.

```python
class SpikeDetector:
    def detect_spike(candle: dict, levels: dict) -> dict:
        """
        Detect if price movement is a real or fake spike
        
        Returns:
            {
                'is_spike': bool,
                'spike_type': 'real' | 'fake' | None,
                'confidence': float
            }
        """
        price_move = abs(candle['close'] - candle['open'])
        points = levels['points']
        
        # Spike if move > 2x points
        if price_move > points * 2:
            # Analyze volume
            avg_volume = get_average_volume(period=20)
            volume_ratio = candle['volume'] / avg_volume
            
            # Analyze candle close relative to extremes
            if candle['close'] > candle['open']:  # Bullish candle
                close_position = (candle['close'] - candle['low']) / (candle['high'] - candle['low'])
            else:  # Bearish candle
                close_position = (candle['high'] - candle['close']) / (candle['high'] - candle['low'])
            
            # Real spike: high volume + close near extreme
            if volume_ratio > 1.5 and close_position > 0.7:
                return {'is_spike': True, 'spike_type': 'real', 'confidence': 0.8}
            else:
                return {'is_spike': True, 'spike_type': 'fake', 'confidence': 0.8}
        
        return {'is_spike': False, 'spike_type': None, 'confidence': 0}
```

### HFT Micro Tick Trader

The HFT module trades using last digit patterns for high-frequency execution.

```python
class HFTMicroTickTrader:
    def extract_micro_levels(price: float) -> dict:
        """
        Extract last digits and calculate micro levels
        
        For price 123456.00:
        - Last digit: 6
        - Last 2 digits: 56
        - Last 3 digits: 456
        """
        price_str = f"{price:.2f}".replace('.', '')
        
        last_1 = int(price_str[-1])
        last_2 = int(price_str[-2:])
        last_3 = int(price_str[-3:])
        
        return {
            'micro': last_1 * 0.2611,
            'mini': last_2 * 0.2611,
            'standard': last_3 * 0.2611
        }
    
    def should_hft_trade(current_price: float, micro_levels: dict) -> dict:
        """
        Determine if HFT trade should be placed
        
        Returns:
            {
                'should_trade': bool,
                'direction': 'long' | 'short',
                'target_profit': float,
                'stop_loss': float
            }
        """
        # Check if price crossed micro level
        last_price = get_last_price()
        
        if current_price > last_price + micro_levels['micro']:
            return {
                'should_trade': True,
                'direction': 'long',
                'target_profit': current_price * 1.002,  # 0.2% profit
                'stop_loss': current_price * 0.9995  # 0.05% stop
            }
        
        return {'should_trade': False, 'direction': None, 'target_profit': 0, 'stop_loss': 0}
```

## Data Models

### Trade Record

```python
@dataclass
class Trade:
    id: str
    timestamp: datetime
    instrument: str
    direction: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    quantity: float
    entry_level: str  # 'BU1', 'BE1', etc.
    exit_level: str
    profit_loss: float
    profit_loss_percent: float
    timeframe: str  # '1m', '5m', '15m'
    mode: str  # 'soft', 'smooth', 'aggressive'
    stop_loss: float
    was_pyramided: bool
    pyramid_count: int
```

### Level Record

```python
@dataclass
class LevelRecord:
    id: str
    timestamp: datetime
    instrument: str
    timeframe: str
    base_price: float
    factor: float
    points: float
    bu1: float
    bu2: float
    bu3: float
    bu4: float
    bu5: float
    be1: float
    be2: float
    be3: float
    be4: float
    be5: float
```

### Position Record

```python
@dataclass
class Position:
    id: str
    instrument: str
    direction: str
    entry_price: float
    current_price: float
    quantity: float
    initial_quantity: float
    entry_time: datetime
    stop_loss: float
    take_profit: list[float]  # Multiple TP levels
    unrealized_pnl: float
    levels_used: dict
    pyramid_history: list[dict]
```

### Pattern Record

```python
@dataclass
class Pattern:
    id: str
    pattern_type: str  # 'level_rejection', 'breakout', 'reversal'
    level: str  # 'BU1', 'BU2', etc.
    success_rate: float
    conditions: dict  # Price action, volume, time of day
    timestamp: datetime
    occurrences: int
```

### Performance Metrics

```python
@dataclass
class PerformanceMetrics:
    date: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    by_instrument: dict
    by_timeframe: dict
    by_mode: dict
```

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Level Calculation Correctness

*For any* base price and timeframe, calculating levels then recalculating with the same base price should produce identical level values.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

### Property 2: Factor Selection Determinism

*For any* base price, the selected factor should be: 26.11% if price < 1000, 2.61% if 1000 ≤ price < 10000, or 0.2611% if price ≥ 10000.

**Validates: Requirements 1.2, 9.1, 9.2, 9.3**

### Property 3: Points Calculation

*For any* base price and factor, Points should equal base_price × factor with precision maintained.

**Validates: Requirements 1.3**

### Property 4: BU Level Ordering

*For any* calculated levels, BU1 < BU2 < BU3 < BU4 < BU5 should always hold.

**Validates: Requirements 1.4**

### Property 5: BE Level Ordering

*For any* calculated levels, BE5 < BE4 < BE3 < BE2 < BE1 < Base should always hold.

**Validates: Requirements 1.5**

### Property 6: Level Symmetry

*For any* base price, the distance from Base to BU1 should equal the distance from Base to BE1.

**Validates: Requirements 1.4, 1.5**

### Property 7: Display Precision

*For any* calculated level value, when formatted for display, it should have exactly 2 decimal places.

**Validates: Requirements 1.8**

### Property 8: Entry Signal Generation

*For any* price that crosses above BU1, a bullish entry signal should be generated; for any price that crosses below BE1, a bearish entry signal should be generated.

**Validates: Requirements 5.1, 5.2**

### Property 9: Non-Trending Day Detection

*For any* price sequence that remains between BE1 and BU1 for 75 consecutive minutes, the system should classify the day as Non_Trending_Day.

**Validates: Requirements 5.8**

### Property 10: Exit Signal at Levels

*For any* long position, when price reaches BU2, BU3, BU4, or BU5, a partial or full exit signal should be generated.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 11: Stop Loss Calculation

*For any* position entry, the stop loss should be calculated as Base_Price + (Points × 0.5) for long positions or Base_Price - (Points × 0.5) for short positions.

**Validates: Requirements 7.1, 7.2, 25.4**

### Property 12: Stop Loss Trigger on Close Only

*For any* candle with a wick below stop loss but close above stop loss, the stop loss should NOT be triggered.

**Validates: Requirements 7.3, 7.4**

### Property 13: Pyramiding Size Limit

*For any* position with pyramiding, the total position size should never exceed 100× the initial position size.

**Validates: Requirements 8.6**

### Property 14: Position Size Calculation

*For any* account capital, risk percentage, and stop loss distance, position size should equal (capital × risk%) / stop_loss_distance.

**Validates: Requirements 17.5**

### Property 15: Daily Loss Limit Enforcement

*For any* trading day, if cumulative losses reach the daily loss limit, no new positions should be opened.

**Validates: Requirements 17.1, 17.3**

### Property 16: Per-Trade Loss Limit Enforcement

*For any* trade, if the loss reaches the per-trade loss limit, the position should be closed immediately.

**Validates: Requirements 17.2, 17.4**

### Property 17: Spike Classification

*For any* candle where price movement exceeds 2× Points, the system should classify it as a potential spike.

**Validates: Requirements 12.1**

### Property 18: Micro Tick Digit Extraction

*For any* price value, extracting last digits should correctly identify the last 1, 2, and 3 digits.

**Validates: Requirements 13.2**

### Property 19: Database Round Trip

*For any* trade record, storing it to trades.db then retrieving it should produce an equivalent trade record.

**Validates: Requirements 18.1**

### Property 20: Level Database Round Trip

*For any* level record, storing it to levels.db then retrieving it should produce an equivalent level record.

**Validates: Requirements 18.4**

### Property 21: Paper Trading No Real Orders

*For any* trade executed in Paper_Trading mode, no real order should be placed with the broker API.

**Validates: Requirements 19.1**

### Property 22: Mode-Based Trade Frequency

*For any* trading day in Soft mode, the number of trades should be between 5-10; in Smooth mode, between 10-30; in Aggressive mode, unlimited.

**Validates: Requirements 26.8, 26.9, 26.10**

### Property 23: Multi-Timeframe Signal Alignment

*For any* instrument, when all three timeframes (1m, 5m, 15m) show the same signal direction, position size should be increased.

**Validates: Requirements 32.2, 32.3**

### Property 24: Order Retry with Exponential Backoff

*For any* failed API request, the system should retry up to 3 times with exponentially increasing delays.

**Validates: Requirements 3.11, 4.9, 30.2**

### Property 25: Limit Order Price Adjustment

*For any* limit order that doesn't fill within 500ms, the price should be adjusted by 1 tick.

**Validates: Requirements 16.3**

### Property 26: Authentication Signature Correctness

*For any* API request to Delta Exchange, the HMAC-SHA256 signature should be correctly calculated using method + timestamp + endpoint.

**Validates: Requirements 3.1, 3.2**

### Property 27: Fibonacci Number Recognition

*For any* price containing Fibonacci digits (23.6, 78.6, etc.), the system should correctly identify and mark them as Fibonacci levels.

**Validates: Requirements 14.1, 14.2, 14.3**

### Property 28: No Indicators Used

*For any* trading decision, the system should use only B5_Factor levels and price/volume data, never technical indicators.

**Validates: Requirements 24.3**

### Property 29: Performance Timing Bounds

*For any* market data update, level calculation should complete within 50ms, signal generation within 100ms, and order placement within 200ms.

**Validates: Requirements 34.1, 34.2, 34.3, 34.4**

### Property 30: Zero Manual Intervention

*For any* normal trading session, the system should operate without requiring manual intervention except for: enabling live trading, emergency stop, or configuration changes.

**Validates: Requirements 35.11**

## Error Handling

### API Connection Failures

**Strategy**: Exponential backoff with retry
- First retry: 1 second delay
- Second retry: 2 seconds delay
- Third retry: 4 seconds delay
- After 3 failures: Log error, alert user, continue with cached data

**Implementation**:
```python
def api_call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except APIError as e:
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                time.sleep(delay)
                continue
            else:
                log_error(f"API call failed after {max_retries} attempts: {e}")
                alert_user("API connection failed")
                raise
```

### Order Placement Failures

**Strategy**: Analyze rejection reason and retry with corrections
- Insufficient funds: Reduce position size
- Invalid price: Adjust to current market price
- Rate limit: Wait and retry
- Other errors: Log and alert

### Database Failures

**Strategy**: Transaction rollback and retry
- Use database transactions for all writes
- Retry up to 3 times on write failure
- If database corrupted, restore from backup
- Maintain daily backups in reports folder

### ML Model Failures

**Strategy**: Graceful degradation to rule-based AUTO SENSE
- If ML model fails to load, use rule-based factor selection
- If prediction fails, use default values
- Continue operating with reduced intelligence
- Alert user to retrain model

### Network Disconnection

**Strategy**: Cache data locally and sync when reconnected
- Cache last known prices and levels
- Mark data as stale with timestamp
- Continue monitoring but don't place new orders
- Sync when connection restored

## Testing Strategy

### Dual Testing Approach

The system requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
- Test specific price values and level calculations
- Test API authentication with known credentials
- Test database operations with sample data
- Test UI rendering with mock data
- Test error handling with simulated failures

**Property-Based Tests**: Verify universal properties across all inputs
- Test level calculations with randomly generated prices
- Test signal generation with random price sequences
- Test position sizing with random capital and risk values
- Test pyramiding limits with random position sizes
- Test stop loss calculations with random entry prices

### Property-Based Testing Configuration

**Library**: Use `hypothesis` for Python property-based testing
**Iterations**: Minimum 100 iterations per property test
**Tagging**: Each property test must reference its design document property

Example property test:
```python
from hypothesis import given, strategies as st

@given(base_price=st.floats(min_value=1, max_value=100000))
def test_level_calculation_correctness(base_price):
    """
    Feature: b5-factor-trading-system, Property 1: Level Calculation Correctness
    
    For any base price, calculating levels twice should produce identical results.
    """
    levels1 = calculate_levels(base_price, '1m')
    levels2 = calculate_levels(base_price, '1m')
    
    assert levels1 == levels2
    assert levels1['bu1'] > levels1['base']
    assert levels1['be1'] < levels1['base']
```

### Unit Testing Balance

Unit tests should focus on:
- Specific examples that demonstrate correct behavior
- Edge cases (price = 0, price = 999.99, price = 1000.00)
- Error conditions (API failures, database errors)
- Integration points between components

Avoid writing too many unit tests for cases covered by property tests. Property tests handle comprehensive input coverage through randomization.

### Test Coverage Goals

- Core calculations: 100% coverage with property tests
- API integrations: 90% coverage with unit tests + mocks
- Database operations: 100% coverage with unit tests
- UI components: 80% coverage with unit tests
- Error handling: 100% coverage with unit tests

### Testing Phases

**Phase 1: Unit Tests for Core Components**
- Level calculator
- Signal generator
- Position manager
- Stop loss calculator

**Phase 2: Property Tests for Correctness**
- All 30 correctness properties
- Run with 100+ iterations each
- Verify no failures

**Phase 3: Integration Tests**
- API integration with test accounts
- Database operations end-to-end
- UI with real-time data simulation

**Phase 4: Paper Trading Validation**
- Run system in paper trading mode for 7 days
- Verify 75%+ accuracy
- Analyze all trades and decisions

**Phase 5: Live Trading with Small Capital**
- Start with $10-50
- Monitor for 24 hours
- Verify system operates correctly
- Scale up if successful
