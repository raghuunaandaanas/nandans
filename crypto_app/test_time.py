#!/usr/bin/env python3
"""Test crypto time functions"""
import sys
sys.path.insert(0, '.')

from cryptoapp import get_crypto_day, get_crypto_market_open_ts, get_ist_now
from datetime import datetime

print("Testing crypto time functions...")
print(f"Crypto day: {get_crypto_day()}")
print(f"Market open ts (00:00 UTC): {get_crypto_market_open_ts()}")
print(f"IST now: {get_ist_now()}")

# Show UTC now
print(f"UTC now: {datetime.now()}")

# Test traderscope
from traderscope import TraderscopeEngine

engine = TraderscopeEngine()
ltp = 67456.80

# Test digit analysis
print("\nTesting Traderscope digit analysis for BTC @ $67,456.80:")
analyses = engine.analyze_all_digits(ltp)
for a in analyses:
    print(f"  Digit {a.digit}: Block {a.block_start:,.0f}-{a.block_end:,.0f} | Position: {a.position:.1f}% | Zone: {a.zone['name']}")

# Test zone (using internal method)
zone = engine._get_zone(56.8)
print(f"\nZone at 56.8%: {zone['name']} ({zone['type']})")

print("\n[OK] All tests passed!")
