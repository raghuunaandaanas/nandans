"""
Real-time First Candle Capture Tool
Run this at market open (5:30 AM IST) to capture first candle closes for all timeframes.
"""

import sys
import time
import requests
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


def get_current_price(symbol: str) -> float:
    """Get current price from Delta Exchange."""
    try:
        url = "https://api.india.delta.exchange/v2/tickers"
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('result'):
                tickers = result['result']
                for ticker in tickers:
                    if ticker.get('symbol') == symbol:
                        return float(ticker.get('close', 0))
        return 0.0
    except:
        return 0.0


def capture_first_candles(symbol: str = 'BTCUSDT'):
    """
    Capture first candle closes at market open.
    
    Instructions:
    1. Run this script at 5:30 AM IST (market open)
    2. Wait for the script to capture all three timeframes
    3. Copy the values and update live_trader.py
    """
    print("="*70)
    print("FIRST CANDLE CAPTURE TOOL")
    print("="*70)
    print(f"\nSymbol: {symbol}")
    print(f"Market Open: 05:30 AM IST")
    print("\nThis tool will capture first candle closes for:")
    print("  - 1m:  at 5:31 AM (after first 1-minute candle closes)")
    print("  - 5m:  at 5:35 AM (after first 5-minute candle closes)")
    print("  - 15m: at 5:45 AM (after first 15-minute candle closes)")
    
    # Storage for captured closes
    captured = {
        '1m': None,
        '5m': None,
        '15m': None
    }
    
    # Capture times (in minutes after market open)
    capture_times = {
        '1m': 1,   # Capture at 5:31 AM
        '5m': 5,   # Capture at 5:35 AM
        '15m': 15  # Capture at 5:45 AM
    }
    
    print("\n" + "="*70)
    print("WAITING FOR MARKET OPEN...")
    print("="*70)
    print("\nPress Ctrl+C to stop\n")
    
    start_time = datetime.now()
    
    try:
        while True:
            current_time = datetime.now()
            elapsed_minutes = (current_time - start_time).total_seconds() / 60
            
            # Get current price
            price = get_current_price(symbol)
            
            timestamp = current_time.strftime("%H:%M:%S")
            print(f"[{timestamp}] Current Price: {price:.2f} | Elapsed: {elapsed_minutes:.1f}m", end='\r')
            
            # Check if we need to capture any timeframe
            for tf, capture_min in capture_times.items():
                if captured[tf] is None and elapsed_minutes >= capture_min:
                    captured[tf] = price
                    print(f"\n✅ [{tf}] First candle close captured: {price:.2f}")
            
            # Check if all captured
            if all(v is not None for v in captured.values()):
                print("\n\n" + "="*70)
                print("ALL FIRST CANDLES CAPTURED!")
                print("="*70)
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Capture stopped by user")
    
    # Display results
    print("\n" + "="*70)
    print("CAPTURED FIRST CANDLE CLOSES")
    print("="*70)
    
    for tf in ['1m', '5m', '15m']:
        if captured[tf]:
            print(f"{tf:>4}: {captured[tf]:.2f}")
        else:
            print(f"{tf:>4}: NOT CAPTURED")
    
    # Generate code to copy
    if all(v is not None for v in captured.values()):
        print("\n" + "="*70)
        print("COPY THESE VALUES TO live_trader.py:")
        print("="*70)
        print(f"MANUAL_BASE_PRICE = {captured['1m']:.2f}     # 1m first candle close (5:31 AM)")
        print(f"MANUAL_BASE_PRICE_5M = {captured['5m']:.2f}  # 5m first candle close (5:35 AM)")
        print(f"MANUAL_BASE_PRICE_15M = {captured['15m']:.2f} # 15m first candle close (5:45 AM)")
        print("="*70)
    else:
        print("\n⚠️  Not all timeframes captured. Run again at market open.")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Capture first candle closes at market open')
    parser.add_argument('--symbol', default='BTCUSDT', help='Trading symbol (default: BTCUSDT)')
    parser.add_argument('--test', action='store_true', help='Test mode - capture immediately')
    
    args = parser.parse_args()
    
    if args.test:
        print("\n⚠️  TEST MODE - Capturing current prices immediately\n")
        time.sleep(2)
        
        symbol = args.symbol
        price = get_current_price(symbol)
        
        print("="*70)
        print("TEST CAPTURE")
        print("="*70)
        print(f"\nCurrent Price: {price:.2f}")
        print("\nUsing same price for all timeframes (for testing only):")
        print(f"MANUAL_BASE_PRICE = {price:.2f}     # 1m")
        print(f"MANUAL_BASE_PRICE_5M = {price:.2f}  # 5m")
        print(f"MANUAL_BASE_PRICE_15M = {price:.2f} # 15m")
        print("\n⚠️  In production, each timeframe will have different closes!")
    else:
        capture_first_candles(args.symbol)


if __name__ == '__main__':
    main()
