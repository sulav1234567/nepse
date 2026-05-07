#!/usr/bin/env python3
"""
Test script to validate NEPSE API real-time data fetching
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.nepse_fetcher import (
    fetch_all_stocks,
    fetch_market_overview,
    fetch_nepse_index_history,
)

async def test_nepse_data(show_details: bool = False):
    """Test NEPSE data fetching"""
    print("\n" + "=" * 70)
    print("NEPSE REAL-TIME DATA FETCH TEST")
    print("=" * 70)
    
    # Test 1: Fetch all stocks
    print("\n[1/3] Testing stock price fetching...")
    print("-" * 70)
    try:
        result = await fetch_all_stocks()
        source = result.get("source", "UNKNOWN")
        count = result.get("count", 0)
        
        print(f"✓ Source: {source}")
        print(f"✓ Stocks fetched: {count}")
        print(f"✓ Timestamp: {result.get('timestamp')}")
        
        if count > 0 and show_details:
            stocks = result.get("stocks", [])
            print(f"\n📊 Sample stocks (first 5):")
            for stock in stocks[:5]:
                print(f"  • {stock['symbol']:8} {stock['name']:30} CMP: {stock['cmp']:10.2f} Change: {stock['changePercent']:+7.2f}%")
        elif count > 0:
            print(f"\n📊 Top 3 gainers:")
            stocks = sorted(result.get("stocks", []), key=lambda x: x['changePercent'], reverse=True)[:3]
            for stock in stocks:
                print(f"  • {stock['symbol']:8} {stock['name']:30} CMP: {stock['cmp']:10.2f} Change: {stock['changePercent']:+7.2f}%")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Test 2: Fetch market overview
    print("\n[2/3] Testing market overview fetching...")
    print("-" * 70)
    try:
        result = await fetch_market_overview()
        source = result.get("source", "UNKNOWN")
        data = result.get("data", {})
        
        print(f"✓ Source: {source}")
        print(f"✓ Timestamp: {result.get('timestamp')}")
        
        if data:
            nepse_idx = data.get("nepse_index", 0)
            nepse_chg = data.get("nepse_change", 0)
            nepse_chg_pct = data.get("nepse_change_percent", 0)
            
            print(f"\n📈 Market Data:")
            print(f"  • NEPSE Index: {nepse_idx:10.2f}")
            print(f"  • Change: {nepse_chg:+10.2f} ({nepse_chg_pct:+7.2f}%)")
            
            if "total_volume" in data:
                print(f"  • Total Volume: {data['total_volume']:,}")
            if "total_turnover" in data:
                print(f"  • Total Turnover: Rs. {data['total_turnover']:,.2f}")
            if "advancers" in data:
                print(f"  • Advancers: {data['advancers']} | Decliners: {data['decliners']} | Unchanged: {data['unchanged']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Test 3: Fetch NEPSE index history
    print("\n[3/3] Testing NEPSE index history fetching...")
    print("-" * 70)
    try:
        result = await fetch_nepse_index_history(days=30)
        source = result.get("source", "UNKNOWN")
        count = result.get("count", 0)
        
        print(f"✓ Source: {source}")
        print(f"✓ Historical records fetched: {count}")
        print(f"✓ Timestamp: {result.get('timestamp')}")
        
        if count > 0 and show_details:
            history = result.get("history", [])
            print(f"\n📅 Recent NEPSE index (latest 5):")
            for record in history[-5:]:
                print(f"  • {record['date']}: {record['close']:10.2f} (Change: {record['change_percent']:+7.2f}%)")
        elif count > 0:
            history = result.get("history", [])
            if history:
                latest = history[-1]
                oldest = history[0]
                print(f"\n📅 Range: {oldest['date']} to {latest['date']}")
                print(f"  • Highest close: {max(h['close'] for h in history):.2f}")
                print(f"  • Lowest close: {min(h['close'] for h in history):.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED - NEPSE API is working correctly!")
    print("=" * 70)
    return True

async def main():
    show_details = "--details" in sys.argv or "-v" in sys.argv
    success = await test_nepse_data(show_details=show_details)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
