"""
B5 Factor Live Trading Bot
Connects to real exchanges and trades with real data.
"""

import sys
import time
import json
from datetime import datetime
from typing import Dict, List

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from src.main import (
    LevelCalculator, SignalGenerator, PositionManager, RiskManager,
    AutoSenseEngine, OrderManager, TradingModeManager, LiveTradingEngine,
    MultiTimeframeCoordinator
)
from src.api_integrations import DeltaExchangeClient, ShoonyaClient
from src.database import DatabaseManager


def get_candle_close(symbol: str, resolution: str, base_url: str = "https://api.india.delta.exchange") -> float:
    """
    Get the FIRST candle's close price at market open (5:30 AM IST).
    Uses the same logic as delta_btc_options.py but returns FIRST candle, not last.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        resolution: Timeframe ('1m', '5m', '15m')
        base_url: Delta Exchange API base URL
        
    Returns:
        First candle close price at market open or None if not available
    """
    try:
        import requests
        import datetime as dt
        
        now_utc = dt.datetime.now(dt.timezone.utc)
        now_ist = now_utc + dt.timedelta(hours=5, minutes=30)
        today_ist = now_ist.replace(hour=5, minute=30, second=0, microsecond=0)
        today_utc = today_ist - dt.timedelta(hours=5, minutes=30)
        start = int(today_utc.timestamp())
        end = start + 3600
        
        url = f"{base_url}/v2/history/candles"
        params = {'symbol': symbol, 'resolution': resolution, 'start': start, 'end': end}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('result'):
                candles = result['result']
                if candles:
                    # Return FIRST candle close (index 0), not last (index -1)
                    return float(candles[0].get('close', 0))
        return None
    except:
        return None


class LiveTradingBot:
    """
    Live trading bot that connects to real exchanges.
    """
    
    def __init__(self, exchange: str = 'delta', mode: str = 'paper'):
        """
        Initialize live trading bot.
        
        Args:
            exchange: 'delta' or 'shoonya'
            mode: 'paper' or 'live'
        """
        print(f"🚀 Initializing B5 Factor Trading Bot...")
        print(f"Exchange: {exchange.upper()}")
        print(f"Mode: {mode.upper()}")
        
        # Initialize components
        self.db = DatabaseManager()
        self.level_calculator = LevelCalculator()
        self.signal_generator = SignalGenerator()
        self.position_manager = PositionManager()
        self.risk_manager = RiskManager()
        self.auto_sense = AutoSenseEngine()
        self.trading_mode = TradingModeManager(initial_mode='smooth')
        self.multi_timeframe = MultiTimeframeCoordinator(self.level_calculator)
        
        # Initialize exchange client
        self.exchange = exchange
        if exchange == 'delta':
            self.api_client = DeltaExchangeClient()
            print("✅ Delta Exchange client initialized")
        else:
            self.api_client = ShoonyaClient()
            print("✅ Shoonya client initialized")
        
        # Initialize order manager and live trading engine
        self.order_manager = OrderManager(self.api_client)
        self.live_engine = LiveTradingEngine(self.api_client, self.db, self.risk_manager)
        
        self.mode = mode
        self.is_running = False
        self.current_positions = {}
        self.levels = {}
        self.levels_5m = {}
        self.levels_15m = {}
        
        # Cache for first candle closes (fetched once per trading day)
        self.first_candle_cache = {}
        
    def connect_to_exchange(self) -> bool:
        """
        Connect to exchange and authenticate.
        
        Returns:
            True if connected successfully
        """
        try:
            print(f"\n🔌 Connecting to {self.exchange.upper()}...")
            
            if self.exchange == 'delta':
                # Test connection by getting products
                products = self.api_client.get_products()
                if products and 'result' in products:
                    print(f"✅ Connected to Delta Exchange")
                    print(f"   Available products: {len(products['result'])}")
                    return True
            else:
                # Test Shoonya connection
                print("⚠️  Shoonya requires manual login")
                print("   Please ensure credentials are valid in shoonya_cred.json")
                return True
                
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            return False
    
    def get_real_time_price(self, symbol: str) -> float:
        """
        Get real-time price from exchange.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price
        """
        try:
            if self.exchange == 'delta':
                ticker = self.api_client.get_ticker(symbol)
                if ticker and 'result' in ticker:
                    result = ticker['result']
                    if 'close' in result:
                        return float(result['close'])
            else:
                quotes = self.api_client.get_quotes('NSE', symbol)
                if quotes and 'lp' in quotes:
                    return float(quotes['lp'])
            
            return 0.0
        except Exception as e:
            print(f"⚠️  Error getting price: {str(e)}")
            return 0.0
    
    def calculate_levels_from_real_data(self, symbol: str, timeframe: str = '1m', 
                                       market_open_time: str = '00:00') -> Dict[str, float]:
        """
        Calculate B5 Factor levels using first candle close at market open.
        Automatically fetches from API and caches for the trading day.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe ('1m', '5m', '15m')
            market_open_time: Market open time in IST format "HH:MM" (e.g., "05:30" for Indian markets)
            
        Returns:
            Dict with calculated levels
        """
        try:
            # Check cache first (fetch once per trading day)
            cache_key = f"{symbol}_{timeframe}"
            if cache_key in self.first_candle_cache:
                base_price = self.first_candle_cache[cache_key]
                print(f"\n[CACHE] Using cached {timeframe} base: {base_price:.2f}")
            else:
                # Fetch from API
                print(f"\n[AUTO-FETCH] Fetching {timeframe} first candle close for {symbol}...")
                base_price = get_candle_close(symbol, timeframe)
                
                if base_price and base_price > 0:
                    print(f"[OK] {timeframe} first candle close: {base_price:.2f}")
                    # Cache it
                    self.first_candle_cache[cache_key] = base_price
                else:
                    # Fallback to current price if first candle not available
                    print(f"[WARN] {timeframe} first candle not available, using current price")
                    base_price = self.get_real_time_price(symbol)
                    # Cache current price too (so it doesn't change every iteration)
                    if base_price > 0:
                        self.first_candle_cache[cache_key] = base_price
            
            if base_price > 0:
                # Calculate levels from base price
                levels = self.level_calculator.calculate_levels(base_price, timeframe)
                
                print(f"\n[LEVELS] Calculated for {symbol} ({timeframe}):")
                print(f"   Base: {levels['base']:.2f}")
                print(f"   BU1: {levels['bu1']:.2f} | BE1: {levels['be1']:.2f}")
                print(f"   BU2: {levels['bu2']:.2f} | BE2: {levels['be2']:.2f}")
                print(f"   BU3: {levels['bu3']:.2f} | BE3: {levels['be3']:.2f}")
                print(f"   BU4: {levels['bu4']:.2f} | BE4: {levels['be4']:.2f}")
                print(f"   BU5: {levels['bu5']:.2f} | BE5: {levels['be5']:.2f}")
                print(f"   Points: {levels['points']:.2f}")
                
                return levels
            
            return {}
            
        except Exception as e:
            print(f"[ERROR] Error calculating levels: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}
    
    def check_for_signals(self, symbol: str, current_price: float, levels: Dict[str, float]) -> Dict[str, any]:
        """
        Check for entry/exit signals using real price.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            levels: Calculated levels
            
        Returns:
            Signal dict with 'signal' key containing 'bullish', 'bearish', or None
        """
        try:
            # Check entry signal
            signal = self.signal_generator.check_entry_signal(
                current_price=current_price,
                levels=levels,
                mode=self.trading_mode.current_mode
            )
            
            # Convert 'buy'/'sell' to 'bullish'/'bearish' for multi-timeframe coordinator
            converted_signal = signal.copy()
            if signal['signal'] == 'buy':
                converted_signal['signal'] = 'bullish'
            elif signal['signal'] == 'sell':
                converted_signal['signal'] = 'bearish'
            
            if converted_signal['signal'] is not None:
                print(f"\n🎯 SIGNAL DETECTED!")
                print(f"   Symbol: {symbol}")
                print(f"   Signal: {signal['signal'].upper()}")  # Show original buy/sell
                print(f"   Price: {current_price:.2f}")
                print(f"   Level: {signal.get('level', 'N/A')}")
                print(f"   Confidence: {signal.get('confidence', 0):.2%}")
            
            return converted_signal
            
        except Exception as e:
            print(f"⚠️  Error checking signals: {str(e)}")
            return {'signal': None}
    
    def execute_trade(self, symbol: str, signal: Dict[str, any], current_price: float) -> bool:
        """
        Execute trade based on signal.
        
        Args:
            symbol: Trading symbol
            signal: Signal dict (with 'bullish'/'bearish' format)
            current_price: Current price
            
        Returns:
            True if trade executed
        """
        try:
            if signal['signal'] is None:
                return False
            
            # Convert bullish/bearish back to buy/sell for execution
            if signal['signal'] == 'bullish':
                trade_direction = 'buy'
            elif signal['signal'] == 'bearish':
                trade_direction = 'sell'
            else:
                return False
            
            # Check if we can trade
            can_trade = self.trading_mode.can_take_trade()
            if not can_trade['can_trade']:
                print(f"⚠️  Cannot trade: {can_trade['reason']}")
                return False
            
            # Calculate position size
            capital = 10000.0  # Starting capital
            risk_percent = 0.01  # 1% risk per trade
            stop_loss_distance = abs(current_price - self.levels.get('base', current_price)) * 0.5
            
            position_size = self.position_manager.calculate_position_size(
                capital=capital,
                risk_percent=risk_percent,
                stop_loss_distance=stop_loss_distance,
                price=current_price
            )
            
            print(f"\n💰 Executing Trade:")
            print(f"   Symbol: {symbol}")
            print(f"   Direction: {trade_direction.upper()}")
            print(f"   Price: {current_price:.2f}")
            print(f"   Size: {position_size:.4f}")
            print(f"   Mode: {self.mode.upper()}")
            
            if self.mode == 'paper':
                print(f"   📝 PAPER TRADE (not real)")
                # Record paper trade
                self.trading_mode.record_trade()
                return True
            else:
                # Execute real trade
                print(f"   🔴 LIVE TRADE (REAL MONEY)")
                
                # Check live trading status
                status = self.live_engine.get_live_status()
                if not status['is_live']:
                    print(f"   ⚠️  Live trading not enabled!")
                    return False
                
                # Place order
                order = self.order_manager.place_market_order(
                    instrument=symbol,
                    side=trade_direction,
                    quantity=position_size
                )
                
                if order['status'] == 'success':
                    print(f"   ✅ Order placed: {order['order_id']}")
                    self.trading_mode.record_trade()
                    return True
                else:
                    print(f"   ❌ Order failed: {order.get('reason', 'Unknown')}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error executing trade: {str(e)}")
            return False
    
    def run_trading_loop(self, symbol: str, interval: int = 5, market_open_time: str = '05:30'):
        """
        Main trading loop - monitors market and trades.
        
        Args:
            symbol: Trading symbol to monitor
            interval: Check interval in seconds
            market_open_time: Market open time in IST format "HH:MM"
        """
        print(f"\n🎬 Starting trading loop...")
        print(f"   Symbol: {symbol}")
        print(f"   Interval: {interval}s")
        print(f"   Mode: {self.mode.upper()}")
        print(f"   Market Open: {market_open_time} IST")
        print(f"\n⚠️  Press Ctrl+C to stop\n")
        
        self.is_running = True
        iteration = 0
        
        try:
            while self.is_running:
                iteration += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"\n{'='*60}")
                print(f"Iteration #{iteration} - {timestamp}")
                print(f"{'='*60}")
                
                # Get real-time price
                current_price = self.get_real_time_price(symbol)
                
                if current_price > 0:
                    print(f"💹 Current Price: {current_price:.2f}")
                    
                    # Calculate levels for all timeframes if not already done
                    if not self.levels:
                        print(f"\n[MULTI-TIMEFRAME] Calculating levels for 1m, 5m, 15m...")
                        self.levels = self.calculate_levels_from_real_data(
                            symbol, '1m', market_open_time
                        )
                    
                    if not self.levels_5m:
                        self.levels_5m = self.calculate_levels_from_real_data(
                            symbol, '5m', market_open_time
                        )
                    
                    if not self.levels_15m:
                        self.levels_15m = self.calculate_levels_from_real_data(
                            symbol, '15m', market_open_time
                        )
                    
                    if self.levels and self.levels_5m and self.levels_15m:
                        # Check signals for all timeframes
                        signal_1m = self.check_for_signals(symbol, current_price, self.levels)
                        signal_5m = self.check_for_signals(symbol, current_price, self.levels_5m)
                        signal_15m = self.check_for_signals(symbol, current_price, self.levels_15m)
                        
                        # Check timeframe alignment
                        alignment = self.multi_timeframe.check_timeframe_alignment(
                            signal_1m, signal_5m, signal_15m
                        )
                        
                        print(f"\n[TIMEFRAME ALIGNMENT]")
                        print(f"   1m: {signal_1m.get('signal', 'neutral')} | 5m: {signal_5m.get('signal', 'neutral')} | 15m: {signal_15m.get('signal', 'neutral')}")
                        print(f"   Aligned: {alignment['aligned']}")
                        print(f"   Direction: {alignment['direction']}")
                        print(f"   Confidence: {alignment['confidence']:.2%}")
                        print(f"   Position Multiplier: {alignment['position_multiplier']}x")
                        print(f"   Reason: {alignment['reason']}")
                        
                        # Only trade if we have a signal and alignment
                        if signal_1m.get('signal') is not None and alignment['aligned']:
                            print(f"   ✅ Taking trade with {alignment['direction']} alignment")
                            self.execute_trade(symbol, signal_1m, current_price)
                        elif signal_1m.get('signal') is not None:
                            print(f"   ⚠️  Skipping trade - timeframes not aligned")
                            print(f"   Directions: {alignment.get('directions', {})}")
                    
                    # Check risk limits
                    risk_check = self.risk_manager.check_daily_loss_limit(0.0, 10000.0)
                    if not risk_check.get('within_limit', True):
                        print(f"\n🛑 RISK LIMIT REACHED - STOPPING")
                        break
                else:
                    print(f"⚠️  Could not get price for {symbol}")
                
                # Wait for next iteration
                print(f"\n⏳ Waiting {interval}s...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Trading stopped by user")
            self.is_running = False
        except Exception as e:
            print(f"\n❌ Error in trading loop: {str(e)}")
            import traceback
            traceback.print_exc()
            self.is_running = False
    
    def enable_live_trading(self):
        """Enable live trading with real money."""
        print(f"\n⚠️  ENABLING LIVE TRADING WITH REAL MONEY")
        print(f"   This will place REAL orders on the exchange!")
        
        response = input("\n   Type 'YES' to confirm: ")
        
        if response == 'YES':
            result = self.live_engine.enable_live_trading(user_confirmation=True)
            if result['enabled']:
                print(f"✅ Live trading enabled")
                self.mode = 'live'
                return True
            else:
                print(f"❌ Could not enable: {result.get('reason', 'Unknown')}")
                return False
        else:
            print(f"❌ Live trading not enabled")
            return False


def main():
    """Main entry point for live trading."""
    print("""
================================================================
                                                              
           B5 FACTOR LIVE TRADING BOT                        
           Real-time Trading System                          
                                                              
================================================================
    """)
    
    # Configuration
    EXCHANGE = 'delta'          # 'delta' or 'shoonya'
    SYMBOL = 'BTCUSDT'          # Trading symbol
    MODE = 'paper'              # 'paper' or 'live'
    INTERVAL = 5                # Check every 5 seconds
    MARKET_OPEN_TIME = '05:30'  # IST time for first candle (05:30 for Indian markets, 00:00 for crypto 24/7)
    
    print(f"⚙️  Configuration:")
    print(f"   Exchange: {EXCHANGE}")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Mode: {MODE}")
    print(f"   Market Open Time: {MARKET_OPEN_TIME} IST")
    print(f"   Check Interval: {INTERVAL}s")
    print(f"\n   ✅ AUTO-FETCH: First candle closes will be fetched automatically")
    
    # Create bot
    bot = LiveTradingBot(exchange=EXCHANGE, mode=MODE)
    
    # Connect to exchange
    if not bot.connect_to_exchange():
        print("❌ Could not connect to exchange. Exiting.")
        return
    
    # Enable live trading if requested
    if MODE == 'live':
        if not bot.enable_live_trading():
            print("❌ Live trading not enabled. Exiting.")
            return
    
    # Start trading
    bot.run_trading_loop(symbol=SYMBOL, interval=INTERVAL, market_open_time=MARKET_OPEN_TIME)
    
    print("\n✅ Trading session ended")


if __name__ == '__main__':
    main()
