#!/usr/bin/env python3
"""
Test the real-time NEPSE index API endpoint
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.nepse_fetcher import fetch_current_nepse_index

async def test_endpoint():
    """Test the real-time NEPSE index endpoint"""
    print("\n" + "="*70)
    print("REAL-TIME NEPSE INDEX ENDPOINT TEST")
    print("="*70 + "\n")
    
    print("Fetching current real-time NEPSE index...")
    print("-"*70)
    
    result = await fetch_current_nepse_index()
    
    print(f"Status: {'✓ SUCCESS' if result.get('nepse_index', 0) > 0 else '✗ FAILED'}")
    print(f"Source: {result.get('source', 'UNKNOWN')}")
    print(f"Timestamp: {result.get('timestamp')}")
    print(f"\nCurrent Data:")
    print(f"  • NEPSE Index:        {result.get('nepse_index', 0):.2f}")
    print(f"  • Change:             {result.get('nepse_change', 0):+.2f}")
    print(f"  • Change Percent:     {result.get('nepse_change_percent', 0):+.2f}%")
    
    if result.get('error'):
        print(f"\nError: {result.get('error')}")
    
    print("\n" + "="*70)
    print("Endpoint will be available at:")
    print("  GET http://127.0.0.1:8000/api/market/nepse-index")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_endpoint())
