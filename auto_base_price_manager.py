"""
Automated Base Price Manager
Automatically fetches and stores first candle closes for all timeframes.
"""

import json
import os
import requests
import datetime as dt
from typing import Dict, Optional


class AutoBasePriceManager:
    """
    Manages automatic fetching and caching of first candle closes.
    """
    
    def __init__(self, cache_file: str = 'base_prices_cache.json'):
        """
        Initialize the manager.
        
        Args:
            cache_file: Path to cache file for storing base prices
        """
        self.cache_file = cache_file
        self.cache = self._load_cache()
        
    def _load_cache(self) -> Dict:
        """Load cached base prices from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save base prices to cache file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"[WARN] Could not save cache: {e}")
    
    def _get_trading_date(self) -> str:
        """Get current trading date in YYYY-MM-DD format (IST)."""
        now_utc = dt.datetime.now(dt.timezone.utc)
        now_ist = now_utc + dt.timedelta(hours=5, minutes=30)
        return now_ist.strftime('%Y-%m-%d')
    
    def _fetch_candle_close(self, symbol: str, resolution: str, 
                           market_open_time: str = '05:30') -> Optional[float]:
        """
        Fetch first candle close at market open using Delta Exchange API.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT', 'BTCUSD')
            resolution: Timeframe ('1m', '5m', '15m')
            market_open_time: Market open time in IST format "HH:MM"
            
        Returns:
            First candle close price or None if not available
        """
        try:
            # Calculate market open time in UTC
            now_utc = dt.datetime.now(dt.timezone.utc)
            now_ist = now_utc + dt.timedelta(hours=5, minutes=30)
            
            # Parse market open time
            hour, minute = map(int, market_open_time.split(':'))
            today_ist = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
            today_utc = today_ist - dt.timedelta(hours=5, minutes=30)
            
            start = int(today_utc.timestamp())
            end = start + 3600  # 1 hour window
            
            # Fetch candles using public API (no auth required)
            url = "https://api.india.delta.exchange/v2/history/candles"
            params = {
                'symbol': symbol,
                'resolution': resolution,
                'start': start,
                'end': end
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('result'):
                    candles = result['result']
                    if candles:
                        # Get the LAST candle's close (most recent before now)
                        return float(candles[-1].get('close', 0))
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch {resolution} candle for {symbol}: {str(e)}")
            return None
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price from Delta Exchange as fallback.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None
        """
        try:
            url = "https://api.india.delta.exchange/v2/tickers"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('result'):
                    tickers = result['result']
                    for ticker in tickers:
                        if ticker.get('symbol') == symbol:
                            return float(ticker.get('close', 0))
            
            return None
        except:
            return None
    
    def get_base_prices(self, symbol: str, market_open_time: str = '05:30',
                       force_refresh: bool = False) -> Dict[str, float]:
        """
        Get base prices for all timeframes (1m, 5m, 15m).
        Uses cache if available for today, otherwise fetches fresh data.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            market_open_time: Market open time in IST format "HH:MM"
            force_refresh: Force refresh even if cache exists
            
        Returns:
            Dict with '1m', '5m', '15m' base prices
        """
        trading_date = self._get_trading_date()
        cache_key = f"{symbol}_{trading_date}"
        
        # Check cache first
        if not force_refresh and cache_key in self.cache:
            cached = self.cache[cache_key]
            print(f"\n[CACHE] Using cached base prices for {symbol} ({trading_date})")
            print(f"   1m:  {cached.get('1m', 0):.2f}")
            print(f"   5m:  {cached.get('5m', 0):.2f}")
            print(f"   15m: {cached.get('15m', 0):.2f}")
            return cached
        
        # Fetch fresh data
        print(f"\n[FETCH] Fetching first candle closes for {symbol}...")
        print(f"   Trading Date: {trading_date}")
        print(f"   Market Open: {market_open_time} IST")
        
        base_prices = {}
        timeframes = ['1m', '5m', '15m']
        
        for tf in timeframes:
            print(f"\n   [{tf}] Fetching...", end=' ')
            price = self._fetch_candle_close(symbol, tf, market_open_time)
            
            if price and price > 0:
                base_prices[tf] = price
                print(f"✅ {price:.2f}")
            else:
                # Fallback to current price
                print(f"⚠️  Not available, using current price...", end=' ')
                current = self._get_current_price(symbol)
                if current and current > 0:
                    base_prices[tf] = current
                    print(f"✅ {current:.2f}")
                else:
                    print(f"❌ Failed")
                    base_prices[tf] = 0
        
        # Save to cache
        if all(v > 0 for v in base_prices.values()):
            self.cache[cache_key] = base_prices
            self._save_cache()
            print(f"\n[CACHE] Saved base prices for {trading_date}")
        else:
            print(f"\n[WARN] Some base prices missing, not caching")
        
        return base_prices
    
    def get_base_price_for_timeframe(self, symbol: str, timeframe: str,
                                    market_open_time: str = '05:30') -> float:
        """
        Get base price for a specific timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: '1m', '5m', or '15m'
            market_open_time: Market open time in IST
            
        Returns:
            Base price for the timeframe
        """
        base_prices = self.get_base_prices(symbol, market_open_time)
        return base_prices.get(timeframe, 0)
    
    def clear_cache(self):
        """Clear all cached base prices."""
        self.cache = {}
        self._save_cache()
        print("[CACHE] Cleared all cached base prices")
    
    def clear_old_cache(self, days: int = 7):
        """
        Clear cache entries older than specified days.
        
        Args:
            days: Number of days to keep
        """
        today = dt.datetime.now()
        cutoff = today - dt.timedelta(days=days)
        
        keys_to_remove = []
        for key in self.cache.keys():
            try:
                # Extract date from key (format: SYMBOL_YYYY-MM-DD)
                date_str = key.split('_')[-1]
                cache_date = dt.datetime.strptime(date_str, '%Y-%m-%d')
                
                if cache_date < cutoff:
                    keys_to_remove.append(key)
            except:
                continue
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            self._save_cache()
            print(f"[CACHE] Removed {len(keys_to_remove)} old entries")


def main():
    """Test the auto base price manager."""
    print("="*70)
    print("AUTO BASE PRICE MANAGER - TEST")
    print("="*70)
    
    manager = AutoBasePriceManager()
    
    # Test with BTCUSDT
    symbol = 'BTCUSDT'
    market_open = '05:30'
    
    print(f"\nFetching base prices for {symbol}...")
    base_prices = manager.get_base_prices(symbol, market_open)
    
    print("\n" + "="*70)
    print("RESULT")
    print("="*70)
    
    if all(v > 0 for v in base_prices.values()):
        print(f"\n✅ Successfully fetched all base prices:")
        print(f"   1m:  {base_prices['1m']:.2f}")
        print(f"   5m:  {base_prices['5m']:.2f}")
        print(f"   15m: {base_prices['15m']:.2f}")
        
        print("\n" + "="*70)
        print("COPY TO live_trader.py:")
        print("="*70)
        print(f"MANUAL_BASE_PRICE = {base_prices['1m']:.2f}")
        print(f"MANUAL_BASE_PRICE_5M = {base_prices['5m']:.2f}")
        print(f"MANUAL_BASE_PRICE_15M = {base_prices['15m']:.2f}")
    else:
        print("\n❌ Failed to fetch some base prices")
        print("   This is normal if market hasn't opened yet")
        print("   or if API doesn't return historical candles")
    
    # Test cache
    print("\n" + "="*70)
    print("TESTING CACHE")
    print("="*70)
    print("\nFetching again (should use cache)...")
    base_prices2 = manager.get_base_prices(symbol, market_open)
    
    if base_prices == base_prices2:
        print("✅ Cache working correctly")
    else:
        print("⚠️  Cache mismatch")


if __name__ == '__main__':
    main()
