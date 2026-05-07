#!/usr/bin/env python3
"""
Test real-time NEPSE index fetching
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import re

SHARESANSAR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.sharesansar.com/",
}

async def test_realtime_nepse():
    """Test fetching real-time NEPSE index"""
    print("\n" + "="*70)
    print("REAL-TIME NEPSE INDEX TEST")
    print("="*70 + "\n")
    
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        # Try Sharesansar
        print("[1] Trying Sharesansar for real-time NEPSE index...")
        try:
            resp = await client.get(
                "https://www.sharesansar.com/today-share-price",
                headers=SHARESANSAR_HEADERS,
                timeout=10.0,
            )
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                page_text = soup.get_text(" ", strip=True)
                
                print(f"Page length: {len(page_text)} chars")
                
                # Look for NEPSE index in various formats
                patterns = [
                    r"NEPSE\s*(?:Index)?\s*(?:\(12\))?\s*:\s*([\d,]+(?:\.\d+)?)",
                    r"Index\s*(?:\(12\))?\s*:\s*([\d,]+(?:\.\d+)?)",
                    r"(?:NEPSE|Index)\D+([\d,]+(?:\.\d+)?)",
                    r"([\d,]+\.[\d]{2})",  # Just float numbers
                ]
                
                found = False
                for i, pattern in enumerate(patterns):
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        value = match.group(1)
                        print(f"✓ Pattern {i+1} found value: {value}")
                        # Try to parse
                        try:
                            num_value = float(value.replace(",", ""))
                            if 500 <= num_value <= 50000:
                                print(f"✓ Valid NEPSE index found: {num_value}")
                                found = True
                                break
                        except:
                            pass
                
                if not found:
                    print("✗ No valid NEPSE index found in patterns")
                    # Show sample of text
                    print(f"\nPage sample (first 500 chars):\n{page_text[:500]}")
                    
                    # Look for price-like patterns
                    prices = re.findall(r"[\d,]+\.[\d]{2}", page_text[:1000])
                    if prices:
                        print(f"\nPrice values found (first 10): {prices[:10]}")
                        
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Try Merolagani
        print("\n[2] Trying Merolagani for real-time NEPSE index...")
        try:
            resp = await client.get(
                "https://www.merolagani.com/LatestMarket.aspx",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://www.merolagani.com/",
                },
                timeout=10.0,
            )
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                page_text = soup.get_text(" ", strip=True)
                
                nepse_match = re.search(r"NEPSE\s*([\d,]+(?:\.\d+)?)", page_text, re.IGNORECASE)
                if nepse_match:
                    value = nepse_match.group(1)
                    print(f"✓ NEPSE value found: {value}")
                    try:
                        num_value = float(value.replace(",", ""))
                        if 500 <= num_value <= 50000:
                            print(f"✓ Valid NEPSE index: {num_value}")
                    except:
                        pass
                else:
                    print("✗ NEPSE pattern not found")
                    print(f"Page sample: {page_text[:500]}")
                    
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(test_realtime_nepse())
