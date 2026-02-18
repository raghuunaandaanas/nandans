"""
Fetch first candle closes for 1m, 5m, and 15m at market open (5:30 AM IST)
"""

import requests
import datetime as dt

def fetch_first_candle(symbol: str, timeframe: str, market_open_time: str = "05:30"):
    """
    Fetch first candle close at market open.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        timeframe: '1m', '5m', or '15m'
        market_open_time: Market open time in IST format "HH:MM"
    
    Returns:
        First candle close price
    """
    try:
        # Calculate today's market open time in IST
        now_utc = dt.datetime.now(dt.timezone.utc)
        now_ist = now_utc + dt.timedelta(hours=5, minutes=30)
        
        # Parse market open time
        hour, minute = map(int, market_open_time.split(':'))
        today_ist = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        today_utc = today_ist - dt.timedelta(hours=5, minutes=30)
        
        start = int(today_utc.timestamp())
        end = start + 3600  # 1 hour window
        
        print(f"\n[{timeframe}] Fetching first candle at {market_open_time} IST...")
        print(f"   UTC timestamp: {start} ({dt.datetime.fromtimestamp(start, dt.timezone.utc)})")
        
        # Fetch candles using public API (no auth)
        url = f"https://api.india.delta.exchange/v2/history/candles"
        params = {
            'symbol': symbol,
            'resolution': timeframe,
            'start': start,
            'end': end
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success') and result.get('result'):
                candles = result['result']
                
                if candles:
                    # Get the first candle
                    first_candle = candles[0]
                    close_price = float(first_candle.get('close', 0))
                    open_price = float(first_candle.get('open', 0))
                    high_price = float(first_candle.get('high', 0))
                    low_price = float(first_candle.get('low', 0))
                    timestamp = first_candle.get('time', 0)
                    
                    candle_time = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
                    candle_time_ist = candle_time + dt.timedelta(hours=5, minutes=30)
                    
                    print(f"   ✅ First candle found:")
                    print(f"      Time: {candle_time_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
                    print(f"      Open: {open_price:.2f}")
                    print(f"      High: {high_price:.2f}")
                    print(f"      Low: {low_price:.2f}")
                    print(f"      Close: {close_price:.2f}")
                    
                    return close_price
                else:
                    print(f"   ⚠️  No candles returned")
                    return None
            else:
                print(f"   ⚠️  API returned error: {result}")
                return None
        else:
            print(f"   ❌ HTTP error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Fetch first candles for all timeframes."""
    print("="*60)
    print("FETCHING FIRST CANDLE CLOSES AT MARKET OPEN")
    print("="*60)
    
    symbol = 'BTCUSDT'
    market_open = '05:30'  # IST
    
    print(f"\nSymbol: {symbol}")
    print(f"Market Open: {market_open} IST")
    
    # Fetch for all timeframes
    timeframes = ['1m', '5m', '15m']
    closes = {}
    
    for tf in timeframes:
        close = fetch_first_candle(symbol, tf, market_open)
        if close:
            closes[tf] = close
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY - First Candle Closes")
    print("="*60)
    
    if closes:
        for tf, close in closes.items():
            print(f"{tf:>4}: {close:.2f}")
        
        print("\n" + "="*60)
        print("UPDATE live_trader.py WITH THESE VALUES:")
        print("="*60)
        print(f"MANUAL_BASE_PRICE = {closes.get('1m', 0):.2f}      # 1m first candle close")
        print(f"MANUAL_BASE_PRICE_5M = {closes.get('5m', 0):.2f}   # 5m first candle close")
        print(f"MANUAL_BASE_PRICE_15M = {closes.get('15m', 0):.2f}  # 15m first candle close")
    else:
        print("\n⚠️  Could not fetch any candles")
        print("   API may not return historical data for today's market open")
        print("   You'll need to manually observe and record the first candle closes")


if __name__ == '__main__':
    main()
