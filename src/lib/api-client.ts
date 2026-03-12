/**
 * NEPSE-ALPHA ULTIMATE — API Client
 * Handles communication with backend FastAPI server
 */

import { Stock } from './types';

// Backend API base URL - defaults to localhost for development
// In production, set NEXT_PUBLIC_API_URL environment variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface LiveDataResponse {
  stocks: Stock[];
  source: 'LIVE' | 'DEMO';
  count: number;
  timestamp: string;
}

export interface MarketOverviewResponse {
  nepseIndex: number;
  change: number;
  changePercent: number;
  totalTurnover: number;
  totalVolume: number;
  advances: number;
  declines: number;
  unchanged: number;
  moneyRates?: {
    interbank: number;
    t91: number;
    t182: number;
    t364: number;
  };
  source: 'LIVE' | 'DEMO';
  timestamp: string;
}

/**
 * Fetch live stock data from backend API
 * Falls back to demo data if backend is unavailable
 */
export async function fetchLiveStocks(): Promise<LiveDataResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/live/stocks`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      // Add timeout and retry logic
      signal: AbortSignal.timeout(10000), // 10 second timeout
    });

    if (!response.ok) {
      throw new Error(`API responded with status ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to fetch live stocks from backend:', error);
    // Return demo data as fallback
    const { DEMO_STOCKS } = await import('./demo-data');
    return {
      stocks: DEMO_STOCKS,
      source: 'DEMO',
      count: DEMO_STOCKS.length,
      timestamp: new Date().toISOString(),
    };
  }
}

/**
 * Fetch live market overview from backend API
 * Falls back to demo data if backend is unavailable
 */
export async function fetchLiveMarket(): Promise<MarketOverviewResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/live/market`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      throw new Error(`API responded with status ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to fetch live market from backend:', error);
    // Return demo market as fallback
    const { DEMO_MARKET_OVERVIEW } = await import('./demo-data');
    return {
      nepseIndex: DEMO_MARKET_OVERVIEW.nepseIndex,
      change: DEMO_MARKET_OVERVIEW.nepseChange,
      changePercent: DEMO_MARKET_OVERVIEW.nepseChangePercent,
      totalTurnover: DEMO_MARKET_OVERVIEW.totalTurnover,
      totalVolume: DEMO_MARKET_OVERVIEW.totalVolume,
      advances: DEMO_MARKET_OVERVIEW.advancers,
      declines: DEMO_MARKET_OVERVIEW.decliners,
      unchanged: DEMO_MARKET_OVERVIEW.unchanged,
      moneyRates: {
        interbank: DEMO_MARKET_OVERVIEW.interbankRate,
        t91: DEMO_MARKET_OVERVIEW.tBillYield,
        t182: DEMO_MARKET_OVERVIEW.tBillYield * 1.1,
        t364: DEMO_MARKET_OVERVIEW.tBillYield * 1.2,
      },
      source: 'DEMO',
      timestamp: new Date().toISOString(),
    };
  }
}

/**
 * Check if backend API is available
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get API base URL for display purposes
 */
export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
