#!/usr/bin/env python3
"""
Debug script to check NEPSE API response details
"""

import asyncio
import sys
import os
import json
import httpx
import certifi

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

NEPSE_BASE = "https://nepalstock.com.np/api/nots"
NEPSE_AUTH_URL = "https://nepalstock.com.np/api/authenticate/prove"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://nepalstock.com.np/",
    "Origin": "https://nepalstock.com.np",
}

async def debug_nepse_api():
    """Debug NEPSE API to see what's happening"""
    print("\n" + "=" * 70)
    print("NEPSE API DEBUG REPORT")
    print("=" * 70)
    
    # Try with SSL verification disabled
    verify_ssl = False  # NEPSE has SSL certificate issues
    
    try:
        async with httpx.AsyncClient(verify=verify_ssl, follow_redirects=True) as client:
            token = None
            
            # Step 1: Try to get auth token
            print("\n[Step 1] Getting NEPSE Authentication Token...")
            print(f"SSL Verification: {verify_ssl}")
            print("-" * 70)
            
            try:
                auth_resp = await client.get(NEPSE_AUTH_URL, headers=HEADERS, timeout=10.0)
                print(f"Status: {auth_resp.status_code}")
                
                if auth_resp.status_code == 200:
                    try:
                        auth_data = auth_resp.json()
                        token = auth_data.get("accessToken")
                        print(f"✓ Token obtained: {token[:50] if token else 'NONE'}...")
                    except json.JSONDecodeError:
                        print(f"⚠ API returned non-JSON response: {auth_resp.text[:200]}")
                else:
                    print(f"✗ HTTP {auth_resp.status_code}: {auth_resp.text[:200]}")
            except Exception as e:
                print(f"✗ Error getting token: {e}")
                token = None

            # Step 2: Try to fetch today's prices
            print("\n[Step 2] Fetching Today's Stock Prices...")
            print("-" * 70)
            
            endpoints = [
                "/nepse-data/today-price",
                "/nepse-data/today-prices",
                "/stock/today-price",
                "/symbol/today-prices",
            ]
            
            for endpoint in endpoints:
                print(f"\nTrying endpoint: {endpoint}")
                try:
                    headers_copy = dict(HEADERS)
                    if token:
                        headers_copy["Authorization"] = f"Salter {token}"
                    
                    resp = await client.get(
                        f"{NEPSE_BASE}{endpoint}",
                        headers=headers_copy,
                        params={"size": 10, "page": 0},
                        timeout=15.0,
                    )
                    print(f"  Status: {resp.status_code}")
                    
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict):
                                print(f"  ✓ Response is JSON dict with keys: {list(data.keys())}")
                                if "content" in data:
                                    print(f"    - content length: {len(data['content'])}")
                                    if data['content']:
                                        print(f"    - First item keys: {list(data['content'][0].keys())}")
                                if "data" in data:
                                    print(f"    - data length: {len(data['data'])}")
                            elif isinstance(data, list):
                                print(f"  ✓ Response is JSON list with {len(data)} items")
                                if data and isinstance(data[0], dict):
                                    print(f"    - First item keys: {list(data[0].keys())}")
                        except json.JSONDecodeError:
                            print(f"  ⚠ Response is not JSON")
                            print(f"  First 300 chars: {resp.text[:300]}")
                    else:
                        print(f"  ✗ HTTP {resp.status_code}")
                        print(f"  Response: {resp.text[:200]}")
                        
                except Exception as e:
                    print(f"  ✗ Error: {e}")

            # Step 3: Check market overview
            print("\n[Step 3] Checking Market Overview Endpoint...")
            print("-" * 70)
            
            try:
                headers_copy = dict(HEADERS)
                if token:
                    headers_copy["Authorization"] = f"Salter {token}"
                
                resp = await client.get(
                    f"{NEPSE_BASE}/market-open",
                    headers=headers_copy,
                    timeout=10.0,
                )
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        print(f"✓ Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                        print(f"Response preview: {json.dumps(data, indent=2)[:500]}")
                    except json.JSONDecodeError:
                        print(f"⚠ Response is not JSON: {resp.text[:200]}")
                else:
                    print(f"Response: {resp.text[:200]}")
            except Exception as e:
                print(f"✗ Error: {e}")
    
    except Exception as e:
        print(f"✗ Fatal error: {e}")

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(debug_nepse_api())

