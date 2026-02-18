# B5 Factor Live Trading Guide

## 🚀 Quick Start - Live Trading with Real Data

This guide will help you start trading with **REAL market data** from exchanges.

---

## ⚠️ IMPORTANT WARNINGS

1. **PAPER TRADING FIRST**: Always test with paper trading before using real money
2. **REAL MONEY RISK**: Live mode trades with REAL money - you can lose your capital
3. **START SMALL**: Begin with minimum capital ($10-50) for live testing
4. **MONITOR CLOSELY**: Watch the bot during initial runs
5. **EMERGENCY STOP**: Press Ctrl+C to stop trading immediately

---

## 📋 Prerequisites

1. **API Credentials**:
   - Delta Exchange: `delta_cred.json` with valid API key and secret
   - Shoonya: `shoonya_cred.json` with valid credentials

2. **Python Dependencies**:
   ```bash
   pip install requests numpy
   ```

3. **Database**: SQLite (included with Python)

---

## 🎯 Running the Live Trader

### Step 1: Paper Trading (SAFE - No Real Money)

```bash
python live_trader.py
```

This will:
- ✅ Connect to Delta Exchange
- ✅ Fetch REAL market prices
- ✅ Calculate B5 Factor levels
- ✅ Generate trading signals
- ✅ Simulate trades (NO real money)
- ✅ Update every 5 seconds

**Output Example:**
```
🚀 Initializing B5 Factor Trading Bot...
Exchange: DELTA
Mode: PAPER

🔌 Connecting to DELTA...
✅ Connected to Delta Exchange
   Available products: 150

🎬 Starting trading loop...
   Symbol: BTCUSD
   Interval: 5s
   Mode: PAPER

====================================================================
Iteration #1 - 2026-02-18 15:30:00
====================================================================
💹 Current Price: 50234.50

📊 Levels calculated for BTCUSD (1m):
   Base: 50234.50
   BU1: 50365.68 | BE1: 50103.32
   BU2: 50496.86 | BE2: 49972.14
   ...

🎯 SIGNAL DETECTED!
   Symbol: BTCUSD
   Signal: BULLISH
   Price: 50365.68
   Level: BU1
   Confidence: 85%

💰 Executing Trade:
   Symbol: BTCUSD
   Direction: bullish
   Price: 50365.68
   Size: 0.0020
   Mode: PAPER
   📝 PAPER TRADE (not real)

⏳ Waiting 5s...
```

### Step 2: Configure for Your Exchange

Edit `live_trader.py` (line 280-283):

```python
# Configuration
EXCHANGE = 'delta'  # 'delta' or 'shoonya'
SYMBOL = 'BTCUSD'   # Trading symbol
MODE = 'paper'      # 'paper' or 'live'
INTERVAL = 5        # Check every 5 seconds
```

**For Delta Exchange:**
- SYMBOL: 'BTCUSD', 'ETHUSD', etc.
- Ensure `delta_cred.json` has valid credentials

**For Shoonya (NSE/BSE):**
- EXCHANGE: 'shoonya'
- SYMBOL: 'NIFTY', 'BANKNIFTY', etc.
- Ensure `shoonya_cred.json` has valid credentials

### Step 3: Live Trading (REAL MONEY - DANGEROUS!)

⚠️ **ONLY after successful paper trading!**

1. Change MODE to 'live':
   ```python
   MODE = 'live'
   ```

2. Run:
   ```bash
   python live_trader.py
   ```

3. Confirm when prompted:
   ```
   ⚠️  ENABLING LIVE TRADING WITH REAL MONEY
      This will place REAL orders on the exchange!
   
      Type 'YES' to confirm: YES
   ```

4. Bot will trade with REAL money:
   ```
   💰 Executing Trade:
      Symbol: BTCUSD
      Direction: bullish
      Price: 50365.68
      Size: 0.0020
      Mode: LIVE
      🔴 LIVE TRADE (REAL MONEY)
      ✅ Order placed: ORD123456
   ```

---

## 🛠️ Configuration Options

### Trading Mode

```python
MODE = 'paper'  # Safe - no real money
MODE = 'live'   # DANGEROUS - real money
```

### Exchange Selection

```python
EXCHANGE = 'delta'    # Delta Exchange (crypto)
EXCHANGE = 'shoonya'  # Shoonya (Indian stocks)
```

### Trading Symbol

```python
# Delta Exchange
SYMBOL = 'BTCUSD'   # Bitcoin
SYMBOL = 'ETHUSD'   # Ethereum

# Shoonya
SYMBOL = 'NIFTY'      # Nifty Index
SYMBOL = 'BANKNIFTY'  # Bank Nifty
```

### Update Interval

```python
INTERVAL = 5   # Check every 5 seconds (fast)
INTERVAL = 60  # Check every 1 minute (slower)
```

### Trading Mode (in bot)

Edit line 265 in `live_trader.py`:
```python
self.trading_mode = TradingModeManager(initial_mode='soft')     # 5-10 trades/day
self.trading_mode = TradingModeManager(initial_mode='smooth')   # 10-30 trades/day
self.trading_mode = TradingModeManager(initial_mode='aggressive') # Unlimited trades
```

---

## 📊 What the Bot Does

1. **Connects to Exchange**: Authenticates with real API
2. **Fetches Real Prices**: Gets live market data every 5 seconds
3. **Calculates Levels**: Uses B5 Factor (0.2611) to calculate BU/BE levels
4. **Detects Signals**: Monitors for BU1/BE1 crosses
5. **Executes Trades**: Places orders when signals detected
6. **Manages Risk**: Enforces daily loss limits (5%), per-trade limits (1%)
7. **Tracks Performance**: Records all trades in database

---

## 🔍 Monitoring

### Real-Time Output

The bot prints:
- Current price updates
- Level calculations
- Signal detections
- Trade executions
- Risk status

### Database Records

All trades saved to:
- `trades.db` - Trade history
- `levels.db` - Level calculations
- `performance.db` - Performance metrics

Query trades:
```python
from src.database import DatabaseManager
db = DatabaseManager()
trades = db.get_trades()
for trade in trades:
    print(trade)
```

---

## 🛑 Stopping the Bot

**Emergency Stop:**
1. Press `Ctrl+C` in terminal
2. Bot stops immediately
3. No new trades placed
4. Existing positions remain open

**Graceful Stop:**
1. Let current iteration complete
2. Press `Ctrl+C`
3. Bot finishes current checks
4. Stops cleanly

---

## ⚙️ Advanced Configuration

### Risk Limits

Edit `live_trader.py` line 265:
```python
self.risk_manager = RiskManager(
    daily_loss_limit=0.05,      # 5% daily loss limit
    per_trade_loss_limit=0.01,  # 1% per trade
    max_exposure=0.20           # 20% max exposure
)
```

### Position Sizing

Edit line 175:
```python
capital = 10000.0        # Starting capital
risk_percent = 0.01      # Risk 1% per trade
```

### Auto-Adjustment

The bot automatically:
- Adjusts limit orders if not filled in 500ms
- Converts to market orders after 3 adjustments
- Trails stop losses as price moves
- Pyramids positions at retracements

---

## 📈 Expected Performance

**Paper Trading (7 days recommended):**
- Target: 75%+ win rate
- Minimum: 50 trades for validation
- Monitor: Daily P&L, drawdown, win rate

**Live Trading (start small):**
- Start: $10-50 capital
- Target: 85%+ win rate with ML
- Scale: Increase capital gradually

---

## 🐛 Troubleshooting

### "Could not connect to exchange"
- Check API credentials in `delta_cred.json` or `shoonya_cred.json`
- Verify internet connection
- Check API key permissions

### "Could not get price"
- Verify symbol name is correct
- Check if market is open
- Ensure exchange API is accessible

### "Cannot trade: Daily limit reached"
- Risk limit hit (5% daily loss)
- Reset: Wait for next trading day
- Or adjust limits in code

### "Order failed"
- Check account balance
- Verify symbol is tradeable
- Check order size (minimum/maximum)

---

## 📞 Support

For issues:
1. Check logs in terminal output
2. Review database records
3. Verify API credentials
4. Test with paper trading first

---

## ⚡ Quick Commands

```bash
# Paper trading (safe)
python live_trader.py

# View trades
python -c "from src.database import DatabaseManager; db = DatabaseManager(); print(db.get_trades())"

# Run tests
python -m pytest tests/ -v

# Check system status
python -c "from live_trader import LiveTradingBot; bot = LiveTradingBot(); bot.connect_to_exchange()"
```

---

## ✅ Checklist Before Live Trading

- [ ] Paper traded for at least 7 days
- [ ] Win rate ≥ 75%
- [ ] Understand B5 Factor levels
- [ ] API credentials verified
- [ ] Risk limits configured
- [ ] Starting with small capital ($10-50)
- [ ] Ready to monitor closely
- [ ] Emergency stop plan ready

---

**Remember: Start with paper trading, test thoroughly, and only use live mode with money you can afford to lose!**
