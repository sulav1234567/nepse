/**
 * Authenticated broker API client (per-user, encrypted credentials on the server).
 * Attaches the JWT from localStorage as a Bearer token.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface MeroShareHolding {
  symbol: string;
  company_name: string;
  units: number;
  ltp: number;
  wacc: number;
  total_cost: number;
  unrealized_gain: number;
  unrealized_gain_pct: number;
}

export interface MeroSharePortfolio {
  holdings: MeroShareHolding[];
  total_value: number;
  total_cost: number;
  total_gain: number;
  total_gain_pct: number;
  fetched_at: string;
}

export interface BrokerStatus {
  connected: boolean;
  provider: string;
  connected_at?: string;
  dp?: string;
  username?: string;
  tms_url?: string;
}

// ─── MeroShare ─────────────────────────────────────────────────────────────────

export function connectMeroShare(dp: string, username: string, password: string) {
  return request<{ connected: boolean; portfolio: MeroSharePortfolio }>(
    '/api/broker/meroshare/connect',
    { method: 'POST', body: JSON.stringify({ dp, username, password }) },
  );
}

export function getMeroShareStatus() {
  return request<BrokerStatus>('/api/broker/meroshare/status');
}

export function getMeroSharePortfolio() {
  return request<MeroSharePortfolio>('/api/broker/meroshare/portfolio');
}

export function disconnectMeroShare() {
  return request<{ connected: boolean }>('/api/broker/meroshare', { method: 'DELETE' });
}

// ─── TMS ───────────────────────────────────────────────────────────────────────

export interface TmsHolding {
  symbol: string;
  quantity: number;
  ltp?: number;
  value?: number;
}

export function connectTms(tmsUrl: string, username: string, password: string, pin?: string) {
  return request<{ connected: boolean }>('/api/broker/tms/connect', {
    method: 'POST',
    body: JSON.stringify({ tms_url: tmsUrl, username, password, pin }),
  });
}

export function getTmsStatus() {
  return request<BrokerStatus>('/api/broker/tms/status');
}

export function getTmsPortfolio() {
  return request<{ holdings: TmsHolding[]; cash_balance: number }>('/api/broker/tms/portfolio');
}

export function disconnectTms() {
  return request<{ connected: boolean }>('/api/broker/tms', { method: 'DELETE' });
}
