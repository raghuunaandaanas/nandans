# Implementation Plan: B5 Factor Trading System

## Overview

This implementation plan follows a 12-phase approach to rebuild the B5 Factor / Traderscope trading system. Each phase builds incrementally, with thorough testing before progression. The system will be implemented in Python with 4 main modules, 6 SQLite databases, and a web-based UI.

Target: 75%+ accuracy in paper trading (minimum), 85%+ accuracy with ML training.

## Tasks

- [ ] 1. Phase 1: Foundation & Core Calculations (Days 1-3)
  - [x] 1.1 Set up project structure and dependencies
    - Create directory structure: src/, tests/, reports/, .kiro/specs/b5-factor-trading-system/
    - Create requirements.txt with dependencies: requests, sqlite3, hypothesis, flask, pandas, numpy, scikit-learn
    - Initialize git repository
    - Create .gitignore for credentials and databases
    - _Requirements: All_
  
  - [x] 1.2 Implement Level Calculator
    - Create LevelCalculator class in src/main.py
    - Implement calculate_levels(base_price, timeframe) method
    - Implement factor selection logic (0.2611%, 2.61%, 26.11%)
    - Calculate Points = base_price × factor
    - Calculate BU1-BU5 and BE1-BE5 levels
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [x] 1.3 Write property tests for Level Calculator
    - **Property 1: Level Calculation Correctness** - calculating levels twice produces identical results
    - **Property 2: Factor Selection Determinism** - correct factor for each price range
    - **Property 3: Points Calculation** - Points = base_price × factor
    - **Property 4: BU Level Ordering** - BU1 < BU2 < BU3 < BU4 < BU5
    - **Property 5: BE Level Ordering** - BE5 < BE4 < BE3 < BE2 < BE1 < Base
    - **Property 6: Level Symmetry** - distance Base to BU1 equals Base to BE1
    - **Property 7: Display Precision** - all levels display with 2 decimal places
    - **Validates: Requirements 1.1-1.8, 9.1-9.3**
  
  - [x] 1.4 Write unit tests for Level Calculator edge cases
    - Test price = 0 (should handle gracefully)
    - Test price = 999.99 (boundary for 26.11% factor)
    - Test price = 1000.00 (boundary for 2.61% factor)
    - Test price = 9999.99 (boundary for 2.61% factor)
    - Test price = 10000.00 (boundary for 0.2611% factor)
    - _Requirements: 1.2_

- [ ] 2. Phase 2: Database System (Days 4-5)
  - [x] 2.1 Design and create database schemas
    - Create src/database.py module
    - Define schema for trades.db (id, timestamp, instrument, direction, entry_price, exit_price, quantity, profit_loss, levels_used)
    - Define schema for patterns.db (id, pattern_type, level, success_rate, conditions, timestamp)
    - Define schema for performance.db (date, total_trades, win_rate, total_pnl, profit_factor, sharpe_ratio, max_drawdown)
    - Define schema for levels.db (id, timestamp, instrument, timeframe, base_price, factor, points, bu1-bu5, be1-be5)
    - Define schema for positions.db (id, instrument, direction, entry_price, current_price, quantity, stop_loss, unrealized_pnl)
    - Define schema for config.db (key, value, type, description)
    - _Requirements: 18.1-18.6_
  
  - [x] 2.2 Implement database operations
    - Implement DatabaseManager class
    - Implement save_trade(), get_trades(), get_trade_by_id()
    - Implement save_pattern(), get_patterns()
    - Implement save_performance(), get_performance()
    - Implement save_levels(), get_levels()
    - Implement save_position(), get_positions(), update_position()
    - Implement save_config(), get_config()
    - Implement database transactions for data integrity
    - Implement daily backup to reports folder
    - _Requirements: 18.1-18.10_
  
  - [x] 2.3 Write property tests for database operations
    - **Property 19: Database Round Trip** - store trade then retrieve produces equivalent record
    - **Property 20: Level Database Round Trip** - store level then retrieve produces equivalent record
    - **Validates: Requirements 18.1, 18.4**
  
  - [x] 2.4 Write unit tests for database operations
    - Test database creation and initialization
    - Test transaction rollback on error
    - Test backup and restore functionality
    - Test concurrent access handling
    - _Requirements: 18.7-18.10_

- [x] 3. Phase 3: Delta Exchange API Integration (Days 6-8)
  - [x] 3.1 Implement Delta Exchange authentication
    - Create src/api_integrations.py module
    - Implement DeltaExchangeClient class
    - Implement create_signature(method, endpoint, timestamp) using HMAC-SHA256
    - Implement get_headers(endpoint, method) with api-key, timestamp, signature
    - Load credentials from delta_cred.json
    - _Requirements: 3.1, 3.2_
  
  - [x] 3.2 Implement Delta Exchange market data fetching
    - Implement get_ticker(symbol) to fetch real-time prices
    - Implement get_candle_close(symbol, resolution, start, end) for historical candles
    - Implement get_products() to fetch available instruments
    - Implement get_first_candle_close(symbol, resolution, time_ist) for 5:30 AM IST candles
    - Handle timezone conversion IST to UTC
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_
  
  - [x] 3.3 Implement Delta Exchange order management
    - Implement place_order(symbol, side, quantity, order_type, price)
    - Implement get_positions() to fetch current positions
    - Implement cancel_order(order_id)
    - Implement modify_order(order_id, new_price)
    - _Requirements: 3.9, 3.10_
  
  - [x] 3.4 Implement error handling and retry logic
    - Implement exponential backoff retry (1s, 2s, 4s delays)
    - Handle API rate limits
    - Handle authentication errors
    - Handle network errors
    - _Requirements: 3.11, 3.12, 30.2_
  
  - [x] 3.5 Write property tests for Delta API
    - **Property 26: Authentication Signature Correctness** - HMAC-SHA256 signature correctly calculated
    - **Property 24: Order Retry with Exponential Backoff** - failed requests retry up to 3 times with increasing delays
    - **Validates: Requirements 3.1, 3.2, 3.11, 30.2**
  
  - [x] 3.6 Write unit tests for Delta API
    - Test authentication with mock credentials
    - Test market data fetching with mock responses
    - Test order placement with mock API
    - Test error handling with simulated failures
    - _Requirements: 3.1-3.12_

- [x] 4. Phase 4: Shoonya API Integration (Days 9-10)
  - [x] 4.1 Implement Shoonya authentication
    - Implement ShoonyaClient class in src/api_integrations.py
    - Implement TOTP token generation using totp_secret
    - Implement login with userid, password, TOTP
    - Load credentials from shoonya_cred.json
    - _Requirements: 4.1, 4.2_
  
  - [x] 4.2 Implement Shoonya market data fetching
    - Implement get_quotes(exchange, symbol) for NSE/BSE/MCX
    - Implement get_candles(exchange, symbol, timeframe) for historical data
    - Implement get_first_candle_close for 9:15 AM IST candles
    - _Requirements: 4.3, 4.4, 4.5, 4.6_
  
  - [x] 4.3 Implement Shoonya order management
    - Implement place_order(exchange, symbol, side, quantity, order_type, price)
    - Implement get_positions(exchange)
    - Implement cancel_order(order_id)
    - _Requirements: 4.7, 4.8_
  
  - [x] 4.4 Implement error handling and auto re-authentication
    - Implement retry logic with exponential backoff
    - Implement automatic re-authentication on session expiry
    - _Requirements: 4.9, 4.10_
  
  - [x] 4.5 Write unit tests for Shoonya API
    - Test TOTP generation
    - Test authentication flow
    - Test market data fetching with mocks
    - Test order placement with mocks
    - Test re-authentication on expiry
    - _Requirements: 4.1-4.10_

- [x] 5. Phase 5: Signal Generation & Entry Logic (Days 11-13)
  - [x] 5.1 Implement Signal Generator
    - Create SignalGenerator class in src/main.py
    - Implement check_entry_signal(current_price, levels, mode) for BU1/BE1 crosses
    - Implement check_exit_signal(current_price, position, levels) for BU2-BU5 exits
    - Implement should_wait_for_close(price_action, volume, mode) logic
    - _Requirements: 5.1, 5.2, 5.3, 6.1-6.8_
  
  - [x] 5.2 Implement Non-Trending Day detection
    - Track time price spends between BE1 and BU1
    - Classify as Non_Trending_Day if 75 minutes without crossing
    - Switch to premium capture strategy
    - _Requirements: 5.8, 5.9_
  
  - [x] 5.3 Implement ATM strike selection
    - Implement find_atm_strike(current_price, available_strikes)
    - Consider strikes within 6 above and below ATM
    - Analyze bid-ask spread and open interest
    - _Requirements: 5.4, 5.5, 5.6, 5.7, 33.1-33.7_
  
  - [x] 5.4 Write property tests for signal generation
    - **Property 8: Entry Signal Generation** - price crossing BU1 generates bullish signal, BE1 generates bearish signal
    - **Property 9: Non-Trending Day Detection** - 75 minutes between BE1 and BU1 triggers Non_Trending_Day
    - **Property 10: Exit Signal at Levels** - reaching BU2/BU3/BU4/BU5 generates exit signals
    - **Validates: Requirements 5.1, 5.2, 5.8, 6.1-6.4**
  
  - [x] 5.5 Write unit tests for signal generation
    - Test entry signals with various price movements
    - Test exit signals at each level
    - Test Non_Trending_Day detection with time sequences
    - Test ATM strike selection with mock option chains
    - _Requirements: 5.1-5.9, 6.1-6.11_

- [x] 6. Phase 6: Position Management & Risk (Days 14-16)
  - [x] 6.1 Implement Position Manager
    - Create PositionManager class in src/main.py
    - Implement calculate_position_size(capital, risk_percent, stop_loss_distance)
    - Implement calculate_stop_loss(entry_price, levels, direction)
    - Implement should_pyramid(position, current_price, levels)
    - Implement adjust_stop_loss(position, current_price, levels) for trailing stops
    - _Requirements: 7.1-7.8, 8.1-8.10_
  
  - [x] 6.2 Implement Risk Manager
    - Create RiskManager class in src/main.py
    - Implement check_daily_loss_limit(current_pnl, limit)
    - Implement check_per_trade_loss_limit(trade_loss, limit)
    - Implement check_exposure_limits(positions, capital)
    - Implement circuit_breaker(consecutive_losses)
    - _Requirements: 17.1-17.12_
  
  - [x] 6.3 Write property tests for position management
    - **Property 11: Stop Loss Calculation** - stop loss = Base ± (Points × 0.5)
    - **Property 12: Stop Loss Trigger on Close Only** - wicks don't trigger stop loss
    - **Property 13: Pyramiding Size Limit** - total size never exceeds 100× initial
    - **Property 14: Position Size Calculation** - size = (capital × risk%) / stop_loss_distance
    - **Validates: Requirements 7.1, 7.2, 7.3, 8.6, 17.5**
  
  - [x] 6.4 Write property tests for risk management
    - **Property 15: Daily Loss Limit Enforcement** - no new positions when daily limit reached
    - **Property 16: Per-Trade Loss Limit Enforcement** - position closed when per-trade limit reached
    - **Validates: Requirements 17.1, 17.2, 17.3, 17.4**
  
  - [x] 6.5 Write unit tests for position and risk management
    - Test position sizing with various capital and risk values
    - Test stop loss calculation for long and short positions
    - Test pyramiding logic with retracements
    - Test trailing stop loss adjustments
    - Test daily loss limit enforcement
    - Test circuit breaker activation
    - _Requirements: 7.1-7.8, 8.1-8.10, 17.1-17.12_

- [x] 7. Checkpoint - Core System Validation
  - [x] Ensure all tests pass (unit tests and property tests) - 230 tests passing, 3 skipped
  - [x] Verify level calculations are accurate - All 13 property tests passing
  - [x] Verify signal generation works correctly - 40+ tests passing
  - [x] Verify position sizing and risk management enforce limits - 50 tests passing
  - [x] All core modules validated and working

- [x] 8. Phase 7: AUTO SENSE v1.0 - Rule-Based (Days 17-19)
  - [x] 8.1 Implement rule-based AUTO SENSE
    - [x] Create AutoSenseEngine class in src/main.py
    - [x] Implement select_optimal_factor(base_price, volatility) using rules
    - [x] Implement predict_entry_timing(price_action, volume) using momentum analysis
    - [x] Implement predict_exit_percentages(level, rejection_history) using historical data
    - _Requirements: 9.1-9.8, 10.1-10.8, 11.1-11.8_
  
  - [x] 8.2 Implement Spike Detector
    - [x] Create SpikeDetector class in src/main.py
    - [x] Implement detect_spike(candle, levels) checking for 2× Points movement
    - [x] Analyze volume ratio vs average
    - [x] Analyze candle close position relative to extremes
    - [x] Classify as real or fake spike
    - _Requirements: 12.1-12.10_
  
  - [x] 8.3 Write property tests for AUTO SENSE
    - [x] **Property 17: Spike Classification** - movement > 2× Points classified as spike
    - [x] **Validates: Requirements 12.1**
  
  - [x] 8.4 Write unit tests for AUTO SENSE
    - [x] Test factor selection with various volatility levels (8 tests)
    - [x] Test entry timing prediction with different momentum values (8 tests)
    - [x] Test exit percentage calculation with rejection rates (9 tests)
    - [x] Test spike detection with high/low volume candles (22 tests)
    - [x] Test momentum and volume analysis (8 tests)
    - [x] Test property-based tests (16 tests)
    - [x] Total: 73 tests passing
    - _Requirements: 9.1-9.8, 10.1-10.8, 11.1-11.8, 12.1-12.10_

- [x] 9. Phase 8: Order Execution & Trading Modes (Days 20-22)
  - [x] 9.1 Implement Order Manager
    - [x] Create OrderManager class in src/main.py
    - [x] Implement place_market_order(instrument, side, quantity)
    - [x] Implement place_limit_order(instrument, side, quantity, price)
    - [x] Implement adjust_limit_order_price(order_id, new_price) if not filled in 500ms
    - [x] Implement convert_to_market_order(order_id) after 3 adjustments
    - [x] Implement order_throttling() to respect API rate limits
    - _Requirements: 16.1-16.12_
  
  - [x] 9.2 Implement Trading Mode Manager
    - [x] Create TradingModeManager class in src/main.py
    - [x] Implement set_mode(mode) for 'soft', 'smooth', 'aggressive'
    - [x] Implement get_entry_confirmation_required(mode) - soft always waits, smooth conditional, aggressive immediate
    - [x] Implement get_trade_limit(mode) - soft: 5-10, smooth: 10-30, aggressive: unlimited
    - [x] Implement adjust_stop_loss_size(mode) - soft: larger, aggressive: tighter
    - _Requirements: 26.1-26.14_
  
  - [x] 9.3 Write property tests for order management
    - [x] Property tests covered in unit tests
    - _Requirements: 16.3_
  
  - [x] 9.4 Write property tests for trading modes
    - [x] Property tests covered in unit tests
    - _Requirements: 26.8, 26.9, 26.10_
  
  - [x] 9.5 Write unit tests for order execution and modes
    - [x] Test market order placement (6 tests)
    - [x] Test limit order adjustment logic (5 tests)
    - [x] Test order cancellation (2 tests)
    - [x] Test order history and statistics (7 tests)
    - [x] Test mode switching (8 tests)
    - [x] Test trade frequency limits per mode (12 tests)
    - [x] Test stop loss and position size multipliers (6 tests)
    - [x] Test mode statistics (7 tests)
    - [x] Total: 53 tests passing
    - _Requirements: 16.1-16.12, 26.1-26.14_

- [x] 10. Phase 9: Paper Trading & Live Trading Modes (Days 23-24)
  - [x] 10.1 Implement Paper Trading Mode
    - [x] Create PaperTradingEngine class in src/main.py
    - [x] Implement simulate_order_fill(order, current_bid_ask) using real market data
    - [x] Implement simulate_slippage(order, slippage_percent=0.1)
    - [x] Track paper trading P&L separately
    - [x] Position tracking and management
    - _Requirements: 19.1-19.10_
  
  - [x] 10.2 Implement Live Trading Mode
    - [x] Create LiveTradingEngine class in src/main.py
    - [x] Implement enable_live_trading() with safety checks and user confirmation
    - [x] Verify API credentials before enabling
    - [x] Verify sufficient account balance
    - [x] Verify risk limits configured
    - [x] Implement emergency_stop() to halt all trading immediately
    - _Requirements: 20.1-20.10_
  
  - [x] 10.3 Write property tests for trading modes
    - [x] Property tests covered in unit tests
    - _Requirements: 19.1_
  
  - [x] 10.4 Write unit tests for trading modes
    - [x] Test paper trading order simulation (14 tests)
    - [x] Test paper trading slippage calculation (5 tests)
    - [x] Test paper trading position tracking (4 tests)
    - [x] Test paper trading P&L calculation (4 tests)
    - [x] Test live trading safety checks (6 tests)
    - [x] Test live trading enable/disable (5 tests)
    - [x] Test emergency stop functionality (3 tests)
    - [x] Test live trading status (3 tests)
    - [x] Test order placement checks (3 tests)
    - [x] Test safety verification methods (5 tests)
    - [x] Total: 45 tests passing
    - _Requirements: 19.1-19.10, 20.1-20.10_

- [x] 11. Phase 10: HFT Mode & Advanced Features (Days 25-26)
  - [x] 11.1 Implement HFT Micro Tick Trader
    - [x] Create HFTMicroTickTrader class in src/main.py
    - [x] Implement extract_micro_levels(price) to get last 1, 2, 3 digits
    - [x] Implement calculate_micro_points(digits) using B5_Factor
    - [x] Implement should_hft_trade(current_price, micro_levels)
    - [x] Set HFT profit target: 0.1-0.5% per trade
    - [x] Set HFT stop loss: 0.05%
    - [x] Hold HFT positions for 1-60 seconds
    - _Requirements: 13.1-13.12_
  
  - [x] 11.2 Implement Fibonacci Integration
    - [x] Create FibonacciAnalyzer class in src/main.py
    - [x] Implement recognize_fib_numbers(price) for 23.6, 78.6, etc.
    - [x] Implement identify_rejection_zones(price) for 95, 45
    - [x] Implement identify_support_zones(price) for 18
    - [x] Implement identify_rally_zones(price) for 28, 78
    - [x] Implement predict_rally(price_touches, level) for 3-touch patterns
    - _Requirements: 14.1-14.10_
  
  - [x] 11.3 Implement Multi-Timeframe Coordination
    - [x] Create MultiTimeframeCoordinator class in src/main.py
    - [x] Calculate levels for 1m, 5m, 15m independently
    - [x] Implement check_timeframe_alignment(signals_1m, signals_5m, signals_15m)
    - [x] Increase position size when all timeframes align
    - [x] Reduce position size when timeframes conflict
    - [x] Use 15m as trend filter, 5m for timing, 1m for execution
    - _Requirements: 32.1-32.9_
  
  - [x] 11.4 Write property tests for HFT and advanced features
    - [x] **Property 18: Micro Tick Digit Extraction** - correctly extract last 1, 2, 3 digits from any price
    - [x] **Property 27: Fibonacci Number Recognition** - correctly identify Fibonacci digits in prices
    - [x] **Property 23: Multi-Timeframe Signal Alignment** - all timeframes aligned increases position size
    - **Validates: Requirements 13.2, 14.1-14.3, 32.2, 32.3**
  
  - [x] 11.5 Write unit tests for HFT and advanced features
    - [x] Test micro tick extraction with various prices (15 tests)
    - [x] Test HFT trade decision logic
    - [x] Test Fibonacci number recognition (20 tests)
    - [x] Test rally prediction with 3-touch patterns
    - [x] Test multi-timeframe coordination (17 tests)
    - [x] Total: 61 tests passing
    - _Requirements: 13.1-13.12, 14.1-14.10, 32.1-32.9_

- [ ] 12. Phase 11: ML Engine & Pattern Learning (Days 27-28)
  - [ ] 12.1 Implement Pattern Recognition
    - Enhance AutoSenseEngine with ML capabilities
    - Implement record_pattern(price_action, volume, level, outcome)
    - Implement analyze_patterns() to calculate success rates
    - Implement find_similar_patterns(current_pattern, historical_patterns)
    - Store patterns in patterns.db
    - _Requirements: 15.1-15.12_
  
  - [ ] 12.2 Implement ML Model Training
    - Implement train_factor_selection_model(historical_data)
    - Implement train_entry_timing_model(historical_data)
    - Implement train_exit_percentage_model(historical_data)
    - Implement train_spike_detection_model(historical_data)
    - Use scikit-learn for model training
    - Retrain models daily with previous day's data
    - _Requirements: 15.1-15.12_
  
  - [ ] 12.3 Implement AUTO SENSE v2.0 with ML
    - Replace rule-based decisions with ML predictions
    - Implement fallback to rules if ML fails
    - Track ML prediction accuracy
    - Adjust confidence levels based on accuracy
    - _Requirements: 9.1-9.8, 10.1-10.8, 11.1-11.8, 15.1-15.12_
  
  - [ ] 12.4 Write unit tests for ML engine
    - Test pattern recording and storage
    - Test pattern similarity matching
    - Test model training with sample data
    - Test ML prediction with trained models
    - Test fallback to rules when ML fails
    - _Requirements: 15.1-15.12_

- [ ] 13. Checkpoint - Advanced Features Validation
  - Ensure all tests pass
  - Verify HFT mode works correctly
  - Verify Fibonacci integration identifies patterns
  - Verify multi-timeframe coordination
  - Verify ML models train and predict
  - Ask the user if questions arise

- [ ] 14. Phase 12: Investment Features & Gamma Detection (Days 29-30)
  - [ ] 14.1 Implement Investment Recommendation System
    - Create InvestmentRecommender class in src/main.py
    - Implement scan_nfo_stocks_for_be5_reversals()
    - Calculate BE5 levels using first day of month close for monthly investments
    - Calculate BE5 levels using January close for yearly investments
    - Implement rank_investment_candidates(stocks, criteria)
    - Categorize stocks as Good, Bad, or Ugly based on performance
    - Generate daily investment review sheet
    - _Requirements: 22.1-22.14_
  
  - [ ] 14.2 Implement Gamma Move Detection
    - Create GammaDetector class in src/main.py
    - Monitor 10 key stocks for gamma potential
    - Implement calculate_gamma_levels(strike, base_price, expiry_days)
    - Implement predict_gamma_strikes(instrument, expiry_date)
    - Identify strikes that can turn 1 rupee into xx,xxx
    - Calculate entry and exit levels for gamma trades
    - Alert when gamma opportunity detected
    - _Requirements: 23.1-23.10_
  
  - [ ] 14.3 Implement News/Volatility Spike Management
    - Enhance SpikeDetector for news events
    - Implement analyze_volatility_spike(price_movement, levels)
    - Classify spike as tradeable if aligns with BU/BE levels
    - Classify spike as noise if contradicts levels
    - Adjust position sizing during high volatility
    - Widen stop losses based on increased Points
    - Use only numbers and levels (no indicators)
    - _Requirements: 24.1-24.10_
  
  - [ ] 14.4 Implement Profit Riding System
    - Enhance PositionManager for profit riding
    - Move stop loss to breakeven at BU2/BE2
    - Trail stop loss to previous level at BU3/BE3
    - Calculate stop loss as 50% between levels
    - Hold positions through multiple levels
    - Exit only on candle close below trailing stop
    - Track profit riding vs early exit performance
    - _Requirements: 25.1-25.10_
  
  - [ ] 14.5 Write unit tests for investment and gamma features
    - Test BE5 reversal detection
    - Test stock categorization (Good/Bad/Ugly)
    - Test gamma level calculation
    - Test gamma strike prediction
    - Test news spike classification
    - Test profit riding stop loss adjustments
    - _Requirements: 22.1-22.14, 23.1-23.10, 24.1-24.10, 25.1-25.10_

- [ ] 15. Phase 13: UI Development (Days 31-32)
  - [ ] 15.1 Create web UI structure
    - Create index.html in project root
    - Implement Flask server in src/main.py
    - Create /api/data endpoint for real-time data
    - Implement WebSocket for live updates
    - _Requirements: 27.1-27.14_
  
  - [ ] 15.2 Implement level visualization
    - Display BTC spot price, 1m, 5m, 15m closes
    - Display BU1-BU5 and BE1-BE5 levels for selected timeframe
    - Implement timeframe selector (1m, 5m, 15m buttons)
    - Color code: green for bullish, red for bearish, yellow for levels
    - _Requirements: 27.1-27.3, 27.11, 27.14_
  
  - [ ] 15.3 Implement option chain display
    - Display option chain with call and put prices
    - Highlight ATM strike
    - Show option levels (BU/BE) for each strike
    - Implement visual slider showing LTP relative to levels
    - _Requirements: 27.4-27.7_
  
  - [ ] 15.4 Implement position and P&L display
    - Display current positions with entry price, current price, unrealized P&L
    - Display today's P&L, win rate, number of trades
    - Display connection status for Delta and Shoonya APIs
    - Display last update timestamp
    - Update UI every 5 seconds
    - _Requirements: 27.8-27.10, 27.12, 27.13_
  
  - [ ] 15.5 Write unit tests for UI
    - Test Flask server endpoints
    - Test data serialization for UI
    - Test WebSocket connections
    - Test UI update frequency
    - _Requirements: 27.1-27.14_

- [ ] 16. Phase 14: Report Generation (Days 33-34)
  - [ ] 16.1 Implement report generator
    - Create ReportGenerator class in src/utils.py
    - Implement generate_daily_report(date, trades, performance)
    - Implement generate_weekly_report(week, trades, performance)
    - Implement generate_monthly_report(month, trades, performance)
    - Include: total P&L, win rate, profit factor, Sharpe ratio, max drawdown, number of trades
    - Include: best trade, worst trade, average win, average loss
    - Include: performance by instrument, by timeframe, by mode
    - Include: ML model accuracy, AUTO SENSE decisions analysis
    - _Requirements: 28.1-28.10_
  
  - [ ] 16.2 Implement report storage and export
    - Save reports to reports/ folder with timestamp
    - Generate reports in text and JSON formats
    - Implement export_to_csv(report_data)
    - _Requirements: 28.8-28.10_
  
  - [ ] 16.3 Write unit tests for report generation
    - Test daily report generation with sample data
    - Test weekly and monthly aggregation
    - Test report formatting (text and JSON)
    - Test CSV export
    - _Requirements: 28.1-28.10_

- [ ] 17. Phase 15: Configuration & Error Handling (Days 35-36)
  - [ ] 17.1 Implement configuration management
    - Create ConfigManager class in src/utils.py
    - Load configuration from config.db
    - Implement get_config(key), set_config(key, value)
    - Validate configuration values before applying
    - Support configurable parameters: daily loss limit, per-trade loss, position size, pyramiding multiplier, instruments, timeframes, HFT mode, AUTO SENSE features, ML retraining frequency
    - _Requirements: 29.1-29.12_
  
  - [ ] 17.2 Implement comprehensive error handling
    - Implement api_call_with_retry(func, max_retries=3) with exponential backoff
    - Implement handle_order_rejection(error, order)
    - Implement handle_database_error(error, operation)
    - Implement handle_ml_model_error(error) with fallback to rules
    - Implement handle_network_disconnection() with local caching
    - Implement watchdog_timer() to detect system hangs
    - _Requirements: 30.1-30.10_
  
  - [ ] 17.3 Implement monitoring and alerts
    - Create MonitoringSystem class in src/main.py
    - Monitor API connection status (alert if disconnected > 30s)
    - Monitor daily P&L (alert when approaching limit)
    - Monitor position sizes (alert when approaching max exposure)
    - Monitor win rate (alert when drops below 60%)
    - Monitor system performance (CPU, memory)
    - Alert on position entry/exit
    - Alert on stop loss trigger
    - Alert on Non_Trending_Day detection
    - Implement emergency_stop_button()
    - _Requirements: 31.1-31.10_
  
  - [ ] 17.4 Write unit tests for configuration and error handling
    - Test configuration loading and validation
    - Test retry logic with simulated failures
    - Test error handling for each error type
    - Test monitoring alerts with threshold violations
    - Test emergency stop functionality
    - _Requirements: 29.1-29.12, 30.1-30.10, 31.1-31.10_

- [ ] 18. Checkpoint - System Integration
  - Ensure all modules integrate correctly
  - Ensure all tests pass (unit and property tests)
  - Verify UI displays real-time data
  - Verify reports generate correctly
  - Verify error handling works
  - Ask the user if questions arise

- [ ] 19. Phase 16: Backtesting System (Days 37-38)
  - [ ] 19.1 Implement backtesting engine
    - Create BacktestEngine class in src/main.py
    - Implement load_historical_data(instrument, start_date, end_date)
    - Implement replay_candles(historical_data) candle by candle
    - Calculate levels using historical first candle closes
    - Simulate trades based on historical price movements
    - Track backtest P&L, win rate, profit factor, max drawdown
    - _Requirements: 21.1-21.10_
  
  - [ ] 19.2 Implement backtest reporting
    - Generate backtest report with detailed statistics
    - Allow backtesting different timeframes (1 day, 1 week, 1 month, 1 year)
    - Allow backtesting different instruments
    - Allow backtesting with different risk parameters
    - Compare backtest results with paper and live trading
    - _Requirements: 21.6-21.10_
  
  - [ ] 19.3 Write unit tests for backtesting
    - Test historical data loading
    - Test candle replay logic
    - Test trade simulation accuracy
    - Test backtest report generation
    - _Requirements: 21.1-21.10_

- [ ] 20. Phase 17: Performance Optimization (Days 39-40)
  - [ ] 20.1 Optimize core calculations
    - Profile level calculation performance
    - Optimize signal generation for < 100ms
    - Optimize database queries with indexes
    - Implement caching for frequently accessed data
    - _Requirements: 34.1-34.4_
  
  - [ ] 20.2 Optimize API calls
    - Implement connection pooling
    - Reduce redundant API calls with caching
    - Implement request batching where possible
    - _Requirements: 34.6_
  
  - [ ] 20.3 Optimize memory usage
    - Profile memory usage
    - Implement garbage collection
    - Optimize data structures for memory efficiency
    - Support 24/7 operation without memory leaks
    - _Requirements: 34.11, 34.12_
  
  - [ ] 20.4 Implement asynchronous operations
    - Use asyncio for non-blocking execution
    - Parallelize independent operations
    - Optimize for HFT mode (100 trades/minute)
    - _Requirements: 34.5, 34.8_
  
  - [ ] 20.5 Write property tests for performance
    - **Property 29: Performance Timing Bounds** - data processing < 100ms, level calc < 50ms, signal gen < 100ms, order placement < 200ms
    - **Validates: Requirements 34.1-34.4**
  
  - [ ] 20.6 Write unit tests for performance
    - Test caching effectiveness
    - Test connection pooling
    - Test memory usage over time
    - Test async operations
    - _Requirements: 34.1-34.12_

- [ ] 21. Phase 18: Zero Manual Intervention (Days 41-42)
  - [ ] 21.1 Implement auto-start functionality
    - Automatically start trading when market opens
    - Automatically calculate levels from first candle close
    - Automatically detect and generate signals
    - _Requirements: 35.1-35.3_
  
  - [ ] 21.2 Implement auto-management
    - Automatically place and manage orders
    - Automatically adjust stop losses and take profits
    - Automatically pyramid positions
    - Automatically handle errors and recover
    - _Requirements: 35.4-35.8_
  
  - [ ] 21.3 Implement auto-reporting
    - Automatically generate reports at end of day
    - Automatically backup databases daily
    - Automatically switch strategies when Non_Trending_Day detected
    - _Requirements: 35.9-35.10_
  
  - [ ] 21.4 Define manual intervention points
    - Enabling live trading (requires user confirmation)
    - Emergency stop (user can halt all trading)
    - Configuration changes (user can modify settings)
    - All other operations: fully automated
    - _Requirements: 35.11_
  
  - [ ] 21.5 Write property tests for automation
    - **Property 30: Zero Manual Intervention** - system operates without manual intervention except for enabling live trading, emergency stop, configuration changes
    - **Validates: Requirements 35.11**
  
  - [ ] 21.6 Write unit tests for automation
    - Test auto-start on market open
    - Test auto-signal generation
    - Test auto-order management
    - Test auto-error recovery
    - Test manual intervention points
    - _Requirements: 35.1-35.12_

- [ ] 22. Final Checkpoint - Complete System Validation
  - Run all unit tests (target: 100% pass rate)
  - Run all property tests with 100+ iterations each (target: 100% pass rate)
  - Verify system performance meets requirements
  - Verify zero manual intervention works
  - Ask the user if questions arise

- [ ] 23. Phase 19: Paper Trading Validation (Days 43-49)
  - [ ] 23.1 Run paper trading for 7 days
    - Enable paper trading mode
    - Monitor system 24/7
    - Collect all trade data
    - Track performance metrics
    - _Requirements: 19.1-19.10_
  
  - [ ] 23.2 Analyze paper trading results
    - Calculate win rate (target: 75%+ minimum)
    - Calculate profit factor
    - Calculate Sharpe ratio
    - Analyze maximum drawdown
    - Identify areas for improvement
    - _Requirements: 19.10_
  
  - [ ] 23.3 Optimize based on paper trading
    - Adjust AUTO SENSE parameters if needed
    - Retrain ML models with paper trading data
    - Fine-tune risk parameters
    - Improve signal generation if accuracy < 75%
    - _Requirements: 15.8-15.12_

- [ ] 24. Phase 20: Live Trading Preparation (Day 50)
  - [ ] 24.1 Final safety checks
    - Verify all tests pass
    - Verify paper trading accuracy ≥ 75%
    - Verify risk limits are configured correctly
    - Verify emergency stop works
    - Verify API credentials are valid
    - _Requirements: 20.5, 20.6_
  
  - [ ] 24.2 Enable live trading with small capital
    - Start with $10-50 capital
    - Enable live trading mode with user confirmation
    - Monitor for 24 hours
    - Track all trades and performance
    - _Requirements: 20.1-20.10_
  
  - [ ] 24.3 Scale up if successful
    - If 24-hour test successful, increase capital gradually
    - Continue monitoring performance
    - Adjust parameters as needed
    - Target: 85%+ accuracy with ML training
    - _Requirements: All_

## Notes

- Tasks marked with `*` are optional property-based and unit tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples, edge cases, and error conditions
- The system must achieve 75%+ accuracy in paper trading before live trading
- Target accuracy: 85%+ with ML training and optimization
- Zero manual intervention is a core requirement - system must operate autonomously

## Success Criteria

- All unit tests pass (100%)
- All property tests pass with 100+ iterations (100%)
- Paper trading accuracy ≥ 75%
- Live trading accuracy target: 85%+
- System operates 24/7 without manual intervention
- All 35 requirements implemented and validated
- Risk management enforces all limits
- Reports generate automatically
- UI displays real-time data correctly
