# Crypto Trading App - Delta India Exchange

## Overview

Parallel crypto trading application using **Delta India API** with the same B5 Factor strategies as the Shoonya (NSE/BSE/MCX) app.

## Architecture

```
crypto_app/
├── cryptoapp.py          # Backend - Delta India API client
├── crypto_ui/
│   ├── server.js         # UI server (port 8788)
│   └── public/
│       └── index.html    # Dashboard UI
├── crypto_out/           # Database & snapshots
│   ├── crypto_data.db    # SQLite database
│   └── crypto_snapshot.json
├── runtime/              # State files
├── logs/                 # Application logs
├── app_start.py          # Process manager
├── delta_cred.json       # API credentials
└── README.md            # This file
```

## Features

### 1. Smart Factor Selector
- **micro (0.2611%)**: Standard crypto scalping
- **mini (2.61%)**: High volatility (BTC/ETH often use this)
- **mega (26.11%)**: Extreme moves and reversals
- **smart**: Auto-select based on price movement

### 2. B5 Factor Levels
Same universal calculation:
```
Points = Close × Factor
BU1 = Close + Points
BU2 = Close + 2×Points
BU3 = Close + 3×Points
BU4 = Close + 4×Points
BU5 = Close + 5×Points
BE1 to BE5 = Close - Points×(1 to 5)
```

### 3. Micro-Fibonacci Zones (Traderscope)
Universal zones that work for ALL instruments:
- **28**: Support test (test 3x, then trend)
- **38**: 1st retracement zone
- **45**: Rejection zone (avoid)
- **50**: Midpoint confirmation
- **78**: Trend acceleration
- **88**: Decision point
- **95**: Major rejection

### 4. 24/7 Trading
Crypto markets never sleep - no market close logic.

## Setup

### 1. Install Dependencies
```bash
# Python dependencies
pip install websocket-client psutil

# Node.js (for UI)
# Already required for Shoonya app
```

### 2. Configure Credentials
Create `delta_cred.json`:
```json
{
  "api_key": "your_api_key_here",
  "api_secret": "your_api_secret_here"
}
```

Get credentials from: https://delta.exchange

### 3. Start the App
```bash
# Start crypto app
python app_start.py start

# Check status
python app_start.py status

# View logs
python app_start.py logs

# Stop
python app_start.py stop

# Restart
python app_start.py restart
```

## Access

- **Dashboard**: http://127.0.0.1:8788/
- **API Health**: http://127.0.0.1:8788/api/health
- **Data API**: http://127.0.0.1:8788/api/dashboard

## Parallel Operation with Shoonya

Both apps can run simultaneously:

| App | Port | Database | Market |
|-----|------|----------|--------|
| Shoonya | 8787 | history_out/ | NSE/BSE/MCX |
| Crypto | 8788 | crypto_out/ | Delta India |

## Trading Strategy

### Entry Signals
1. **B5 Level**: Price near BU1-BU5
2. **Micro Zone**: 28-support, 50-midpoint, 78-acceleration
3. **Trend**: UP confirmation
4. **Volume**: Increasing

### Exit Signals
1. **Target**: BU3, BU4, BU5 (rarely)
2. **Stop Loss**: Below BE1 or micro support break
3. **Reversal**: 45 or 95 zone rejection

### Special for Crypto
- Higher volatility → Use mini factor more often
- 24/7 → No market close considerations
- USDT pairs only (for stability)

## API Reference

### Delta India Endpoints
- **REST**: https://api.india.delta.exchange
- **WebSocket**: wss://socket.india.delta.exchange
- **Docs**: https://docs.delta.exchange

### Rate Limits
- Public API: 10 requests/second
- Private API: 20 requests/second
- WebSocket: Real-time stream

## Git Tracking

All changes are tracked in git with detailed commit messages.

```bash
# View recent commits
git log --oneline -10

# View specific file changes
git log -p -- crypto_app/cryptoapp.py
```

## Troubleshooting

### WebSocket Connection Issues
```bash
# Check if port is available
netstat -an | findstr 8788
```

### API Errors
- Check `delta_cred.json` is valid
- Verify API key has trading permissions
- Check rate limits in logs

### Database Issues
```bash
# Reset database (will lose data)
rm crypto_out/crypto_data.db
```

## Performance

- **Symbols**: Top 200 USDT pairs
- **Update Rate**: 2 seconds
- **Memory**: ~200MB
- **CPU**: Low (mostly I/O bound)

## Development

### Adding New Features
1. Edit relevant file
2. Test locally
3. Commit with detailed message
4. Document in README

### Code Structure
- **cryptoapp.py**: Main application logic
- **server.js**: UI API server
- **index.html**: Frontend dashboard

## Support

For issues specific to:
- **Delta API**: Contact Delta India support
- **This App**: Check logs in `logs/` directory

## License

Same as main project (private use).
