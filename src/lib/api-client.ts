/**
 * NEPSE-ALPHA API Client
 * Communicates with the FastAPI backend for real-time data
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiStock {
  symbol: string;
  name: string;
  sector: string;
  cmp: number;
  change: number;
  change_percent: number;
  volume: number;
  pe: number;
  pb: number;
  roe: number;
  dividend_yield: number;
  fvl: number;
  tml: number;
  ssil: number;
  gtbil: number;
  mrlll: number;
  fcs: number;
  signal: string;
}

export interface ApiStocksResponse {
  stocks: ApiStock[];
  source: 'LIVE' | 'DEMO';
  count: number;
}

export interface ApiMarket {
  nepse_index: number;
  nepse_change: number;
  nepse_change_percent: number;
  total_turnover: number;
  total_volume: number;
  total_transactions: number;
  advancers: number;
  decliners: number;
  unchanged: number;
  regime: string;
  regime_confidence: number;
  interbank_rate: number;
  t_bill_yield: number;
  source: 'LIVE' | 'DEMO';
}

export interface ApiSector {
  sector: string;
  index: number;
  change: number;
  change_percent: number;
  volume: number;
}

/**
 * Fetch all stocks with FCS analysis
 */
export async function fetchStocks(sector?: string, sortBy: string = 'fcs'): Promise<ApiStocksResponse> {
  const params = new URLSearchParams();
  if (sector) params.append('sector', sector);
  params.append('sort_by', sortBy);
  
  const response = await fetch(`${API_BASE_URL}/api/stocks?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch stocks: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch market overview
 */
export async function fetchMarket(): Promise<ApiMarket> {
  const response = await fetch(`${API_BASE_URL}/api/market`);
  if (!response.ok) {
    throw new Error(`Failed to fetch market: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch sector performance
 */
export async function fetchSectors(): Promise<ApiSector[]> {
  const response = await fetch(`${API_BASE_URL}/api/market/sectors`);
  if (!response.ok) {
    throw new Error(`Failed to fetch sectors: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch detailed stock analysis
 */
export async function fetchStockAnalysis(symbol: string, tier: string = 'daily') {
  const response = await fetch(`${API_BASE_URL}/api/stocks/${symbol}?tier=${tier}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch stock analysis: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch stock history
 */
export async function fetchStockHistory(symbol: string) {
  const response = await fetch(`${API_BASE_URL}/api/stocks/${symbol}/history`);
  if (!response.ok) {
    throw new Error(`Failed to fetch stock history: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch daily predictions
 */
export async function fetchDailyPredictions() {
  const response = await fetch(`${API_BASE_URL}/api/predictions/daily`);
  if (!response.ok) {
    throw new Error(`Failed to fetch daily predictions: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch weekly predictions
 */
export async function fetchWeeklyPredictions() {
  const response = await fetch(`${API_BASE_URL}/api/predictions/weekly`);
  if (!response.ok) {
    throw new Error(`Failed to fetch weekly predictions: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch monthly predictions
 */
export async function fetchMonthlyPredictions() {
  const response = await fetch(`${API_BASE_URL}/api/predictions/monthly`);
  if (!response.ok) {
    throw new Error(`Failed to fetch monthly predictions: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch portfolio optimization
 */
export async function fetchPortfolio() {
  const response = await fetch(`${API_BASE_URL}/api/portfolio`);
  if (!response.ok) {
    throw new Error(`Failed to fetch portfolio: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch AI predictions
 */
export async function fetchAIPredictions(top: number = 20) {
  const response = await fetch(`${API_BASE_URL}/api/ai/predictions?top=${top}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch AI predictions: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch API health status
 */
export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error(`Failed to fetch health: ${response.statusText}`);
  }
  return response.json();
}
