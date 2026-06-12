/**
 * NEPSE-ALPHA API Client
 * Communicates with the FastAPI backend for real-time data
 */

import { Stock } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
export type ApiDataSource = 'LIVE' | 'LIVE_SCRAPED' | 'LIVE_SCRAPED_MEROLAGANI' | 'UNAVAILABLE' | 'CACHED' | 'UNKNOWN';

const FETCH_OPTIONS: RequestInit = {
  cache: 'no-store',
};

function normalizeDataSource(value: unknown): ApiDataSource {
  if (
    value === 'LIVE' ||
    value === 'LIVE_SCRAPED' ||
    value === 'LIVE_SCRAPED_MEROLAGANI' ||
    value === 'UNAVAILABLE'
  ) {
    return value;
  }

  return 'UNKNOWN';
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, FETCH_OPTIONS);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}: ${response.statusText}`);
  }
  return response.json();
}

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
  source: ApiDataSource;
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
  source: ApiDataSource;
  timestamp?: string;
}

export interface ApiMarketWarning {
  level: string;
  title: string;
  message: string;
}

export interface ApiMarketLeader {
  sector: string;
  avg_change: number;
  median_change: number;
  breadth: number;
  count: number;
  turnover_proxy: number;
  leadership_score: number;
}

export interface ApiMarketIntelligence {
  bias: string;
  action: string;
  breadth_ratio: number;
  up_volume_share: number;
  average_change: number;
  median_change: number;
  dispersion: number;
  trend_score: number;
  liquidity_score: number;
  volatility_score: number;
  froth_score: number;
  crash_risk: number;
  crash_level: string;
  bull_probability: number;
  bear_probability: number;
  support_low: number;
  support_high: number;
  resistance_low: number;
  resistance_high: number;
  concentration_risk: number;
  warnings: ApiMarketWarning[];
  opportunities: string[];
  sector_leaders: ApiMarketLeader[];
  sector_laggards: ApiMarketLeader[];
  snapshot_stats: {
    stocks: number;
    advancers: number;
    decliners: number;
    unchanged: number;
    upside_tail: number;
    downside_tail: number;
    average_volume_ratio: number;
  };
}

export interface ApiMarketIntelligenceResponse {
  market: ApiMarket;
  intelligence: ApiMarketIntelligence;
  source: ApiDataSource;
  timestamp?: string;
}

export interface ApiAutonomousArchitectureComponent {
  name: string;
  layer: string;
  description: string;
  technologies: string[];
}

export interface ApiAutonomousStatus {
  as_of: string;
  database_backend: string;
  timescaledb_active: boolean;
  latest_ingestion_at?: string | null;
  latest_training_at?: string | null;
  latest_scoring_at?: string | null;
  bootstrap_mode: boolean;
  symbols_covered: number;
  bars_loaded: number;
  fundamentals_loaded: number;
  macro_points_loaded: number;
  news_articles_loaded: number;
  retrain_required: boolean;
}

export interface ApiAutonomousRegime {
  regime: 'BULL' | 'BEAR' | 'SIDEWAYS' | 'DISTRIBUTION' | 'CRISIS';
  confidence: number;
  trend_score: number;
  volatility_score: number;
  breadth_score: number;
  liquidity_score: number;
  explanation: string;
}

export interface ApiAutonomousMonitoringMetric {
  horizon: string;
  directional_accuracy: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
}

export interface ApiAutonomousSectorRotation {
  sector: string;
  rotation_score: number;
  leadership_score: number;
  momentum_score: number;
  valuation_score: number;
  liquidity_score: number;
  signal: string;
  commentary: string;
}

export interface ApiAutonomousCorrelationSignal {
  series: string;
  lag_days: number;
  correlation: number;
  latest_direction: string;
  impact: string;
}

export interface ApiAutonomousSignalCard {
  as_of: string;
  symbol: string;
  company_name: string;
  sector: string;
  overall_signal: 'STRONG BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG SELL';
  confidence_score: number;
  predicted_targets: {
    target_7d: number;
    target_30d: number;
    target_90d: number;
  };
  expected_return_percent: number;
  risk_adjusted_return: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'VERY HIGH';
  technical: {
    technical_score: number;
    rsi_14: number;
    macd_histogram: number;
    bollinger_position: number;
    adx: number;
    ema_9: number;
    ema_21: number;
    ema_50: number;
    ema_200: number;
    stochastic_k: number;
    stochastic_d: number;
    obv_slope: number;
    vwap_gap_percent: number;
    support: number;
    resistance: number;
    fibonacci_38_2: number;
    fibonacci_50: number;
    fibonacci_61_8: number;
    ichimoku_bias: string;
    detected_patterns: string[];
  };
  fundamentals: {
    fundamental_score: number;
    eps: number;
    pe: number;
    pb: number;
    dividend_yield: number;
    revenue_growth_yoy: number;
    revenue_growth_qoq: number;
    net_profit_margin: number;
    roe: number;
    roa: number;
    debt_to_equity: number;
    current_ratio: number;
    quick_ratio: number;
    book_value_per_share: number;
    npl_ratio?: number | null;
    casa_ratio?: number | null;
    deterioration_flags: string[];
  };
  global_view: {
    global_sentiment_score: number;
    signals: ApiAutonomousCorrelationSignal[];
    macro_bias: string;
    remittance_tailwind: number;
    policy_rate_trend: number;
    commodity_pressure: number;
    crypto_sentiment: number;
  };
  top_reasons: string[];
  historical_accuracy: number;
  warnings: string[];
  model_votes: Array<{
    model_name: string;
    confidence: number;
    predicted_return_7d: number;
    predicted_return_30d: number;
    predicted_return_90d: number;
    directional_bias: string;
    rationale: string;
  }>;
  liquidity_score: number;
  sentiment_score: number;
  regime_alignment_score: number;
}

export interface ApiAutonomousBacktest {
  strategy_name: string;
  start_date?: string | null;
  end_date?: string | null;
  annualized_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  turnover: number;
}

export interface ApiAutonomousDashboardResponse {
  architecture: ApiAutonomousArchitectureComponent[];
  architecture_diagram: string;
  status: ApiAutonomousStatus;
  regime: ApiAutonomousRegime;
  monitoring: ApiAutonomousMonitoringMetric[];
  sector_rotation: ApiAutonomousSectorRotation[];
  top_buys: ApiAutonomousSignalCard[];
  top_avoids: ApiAutonomousSignalCard[];
  backtest?: ApiAutonomousBacktest | null;
}

export interface ApiIndexHistoryCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
  change_percent: number;
  turnover: number;
}

export interface ApiIndexHistoryResponse {
  source: ApiDataSource;
  history: ApiIndexHistoryCandle[];
  count: number;
  timestamp?: string;
}

export interface ApiIndexAnalysisResponse {
  market: ApiMarket;
  history: ApiIndexHistoryCandle[];
  analysis: {
    bias: string;
    summary: string;
    patterns: ApiCandlestickPattern[];
    warnings: Array<{
      title: string;
      message: string;
    }>;
    signals: {
      close: number;
      day_change_percent: number;
      swing_5d: number;
      swing_20d: number;
      ema9: number;
      ema21: number;
      ema55: number;
      rsi14: number;
      support: number;
      resistance: number;
      rise_probability: number;
      crash_probability: number;
      trend_strength: number;
      volatility: number;
      market_crash_risk: number;
      macd: number;
      bb_pct: number;
      bb_width: number;
      atr_pct: number;
      vol_ratio: number;
      ml_available: boolean;
      latest_date?: string;
    };
  };
  intelligence: ApiMarketIntelligence;
  source: ApiDataSource;
  timestamp?: string;
}

export interface ApiSector {
  sector: string;
  index: number;
  change: number;
  change_percent: number;
  volume: number;
}

export interface ApiCandlestickPattern {
  name: string;
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  strength: number;
  explanation: string;
}

export interface ApiRecommendationPlan {
  action: string;
  confidence: string;
  entry_low: number;
  entry_high: number;
  ideal_entry: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  sell_zone_low: number;
  sell_zone_high: number;
  hold_days_min: number;
  hold_days_max: number;
  expected_upside_percent: number;
  expected_upside_rs: number;
  expected_downside_percent: number;
  expected_downside_rs: number;
  risk_reward_ratio: number;
  time_to_target_days: number;
  exit_trigger: string;
  thesis: string;
  notes: string[];
}

export interface ApiStockAnalysis {
  stock: {
    symbol: string;
    name: string;
    sector: string;
    cmp: number;
    previous_close: number;
    change: number;
    change_percent: number;
    volume: number;
    avg_volume_20d: number;
    high_52w: number;
    low_52w: number;
    open: number;
    high: number;
    low: number;
  };
  indicators: {
    ema9: number;
    ema21: number;
    ema55: number;
    sma200: number;
    rsi14: number;
    macd_line: number;
    macd_signal: number;
    macd_histogram: number;
    stoch_rsi: number;
    obv: number;
    atr14: number;
    volume_ratio: number;
    ema_alignment: string;
  };
  fcs: {
    score: number;
    signal: string;
    layer_scores: {
      fvl: number;
      tml: number;
      ssil: number;
      gtbil: number;
      mrlll: number;
    };
    weights: {
      fvl: number;
      tml: number;
      ssil: number;
      gtbil: number;
      mrlll: number;
    };
    overrides: Array<{
      id: string;
      name: string;
      triggered: boolean;
      description: string;
    }>;
  };
  price_targets: {
    pt1: number;
    pt2: number;
    stop_loss: number;
    trailing_stop_activation: number;
  };
  warning_flags: {
    sis_score: number;
    sis_level: string;
    bmr: number;
    bmr_level: string;
    circular_trading: boolean;
    right_share_phase: string;
    tth_status: string;
    political_risk: string;
    bsts_confidence: string;
  };
  fvl_details: string[];
  tml_details: string[];
  ssil_details: string[];
  gtbil_details: string[];
  mrlll_details: string[];
  overvaluation_percent: number;
  bsts_fair_value: number;
  retail_institutional_verdict: string;
  candlestick_patterns: ApiCandlestickPattern[];
  recommendation: ApiRecommendationPlan | null;
}

export interface ApiHistoryCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LiveStocksResponse {
  stocks: Stock[];
  source: ApiDataSource;
  count: number;
  timestamp?: string;
}

export interface LiveMarketResponse {
  nepseIndex: number;
  change: number;
  changePercent: number;
  totalTurnover: number;
  totalVolume: number;
  totalTransactions: number;
  advances: number;
  declines: number;
  unchanged: number;
  moneyRates?: {
    interbank: number;
    t91: number;
  };
  source: ApiDataSource;
  timestamp?: string;
}

function toNumber(value: unknown, fallback: number = 0): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function normalizeLiveMarketPayload(payload: unknown): LiveMarketResponse {
  const response = (payload ?? {}) as Record<string, unknown>;
  const nestedData = response.data;
  const rawData = (
    nestedData && typeof nestedData === 'object'
      ? (nestedData as Record<string, unknown>)
      : response
  );

  return {
    nepseIndex: toNumber(rawData.nepse_index ?? rawData.index ?? rawData.nepseIndex),
    change: toNumber(rawData.nepse_change ?? rawData.change ?? rawData.nepseChange),
    changePercent: toNumber(rawData.nepse_change_percent ?? rawData.change_percent ?? rawData.changePercent),
    totalTurnover: toNumber(rawData.total_turnover ?? rawData.turnover ?? rawData.totalTurnover),
    totalVolume: toNumber(rawData.total_volume ?? rawData.totalVolume),
    totalTransactions: toNumber(rawData.total_transactions ?? rawData.totalTransactions),
    advances: toNumber(rawData.advancers ?? rawData.advances),
    declines: toNumber(rawData.decliners ?? rawData.declines),
    unchanged: toNumber(rawData.unchanged),
    moneyRates: {
      interbank: toNumber(rawData.interbank_rate ?? rawData.interbankRate),
      t91: toNumber(rawData.t_bill_yield ?? rawData.tBillYield),
    },
    source: normalizeDataSource(response.source),
    timestamp: typeof response.timestamp === 'string' ? response.timestamp : undefined,
  };
}

function toApiMarketFromLiveMarket(payload: LiveMarketResponse): ApiMarket {
  return {
    nepse_index: payload.nepseIndex,
    nepse_change: payload.change,
    nepse_change_percent: payload.changePercent,
    total_turnover: payload.totalTurnover,
    total_volume: payload.totalVolume,
    total_transactions: payload.totalTransactions,
    advancers: payload.advances,
    decliners: payload.declines,
    unchanged: payload.unchanged,
    regime: payload.changePercent >= 1.5 ? 'BULL TREND' : payload.changePercent <= -1.5 ? 'BEAR TREND' : 'SIDEWAYS',
    regime_confidence: Math.min(90, 55 + Math.abs(payload.changePercent) * 10),
    interbank_rate: payload.moneyRates?.interbank ?? 0,
    t_bill_yield: payload.moneyRates?.t91 ?? 0,
    source: payload.source,
    timestamp: payload.timestamp,
  };
}

/**
 * Legacy-compatible helper used across pages to fetch live stock list.
 */
export async function fetchLiveStocks(): Promise<LiveStocksResponse> {
  const data = await fetchJson<Record<string, unknown>>('/api/live/stocks');
  return {
    stocks: (data.stocks ?? []) as Stock[],
    source: normalizeDataSource(data.source),
    count: toNumber(data.count, Array.isArray(data.stocks) ? data.stocks.length : 0),
    timestamp: typeof data.timestamp === 'string' ? data.timestamp : undefined,
  };
}

/**
 * Legacy-compatible helper used across pages to fetch live market summary.
 */
export async function fetchLiveMarket(): Promise<LiveMarketResponse> {
  const data = await fetchJson<unknown>('/api/live/market');
  return normalizeLiveMarketPayload(data);
}

/**
 * Fetch all stocks with FCS analysis
 */
export async function fetchStocks(sector?: string, sortBy: string = 'fcs'): Promise<ApiStocksResponse> {
  const params = new URLSearchParams();
  if (sector) params.append('sector', sector);
  params.append('sort_by', sortBy);

  return fetchJson<ApiStocksResponse>(`/api/stocks?${params}`);
}

/**
 * Fetch market overview
 */
export async function fetchMarket(): Promise<ApiMarket> {
  const primary = await fetchJson<ApiMarket>('/api/market');
  if (toNumber(primary.nepse_index) > 0) {
    return primary;
  }

  const fallback = await fetchLiveMarket();
  return toApiMarketFromLiveMarket(fallback);
}

/**
 * Fetch sector performance
 */
export async function fetchSectors(): Promise<ApiSector[]> {
  return fetchJson<ApiSector[]>('/api/market/sectors');
}

export async function fetchMarketIntelligence(): Promise<ApiMarketIntelligenceResponse> {
  return fetchJson<ApiMarketIntelligenceResponse>('/api/market/intelligence');
}

export async function fetchNepseIndexHistory(days: number = 90): Promise<ApiIndexHistoryResponse> {
  return fetchJson<ApiIndexHistoryResponse>(`/api/market/index-history?days=${days}`);
}

export async function fetchNepseIndexAnalysis(days: number = 90): Promise<ApiIndexAnalysisResponse> {
  return fetchJson<ApiIndexAnalysisResponse>(`/api/market/index-analysis?days=${days}`);
}

/**
 * Fetch detailed stock analysis
 */
export async function fetchStockAnalysis(symbol: string, tier: string = 'daily') {
  return fetchJson<ApiStockAnalysis>(`/api/stocks/${symbol}?tier=${tier}`);
}

/**
 * Fetch stock history
 */
export async function fetchStockHistory(symbol: string) {
  return fetchJson<ApiHistoryCandle[]>(`/api/stocks/${symbol}/history`);
}

/**
 * Fetch daily predictions
 */
export async function fetchDailyPredictions() {
  return fetchJson('/api/predictions/daily');
}

/**
 * Fetch weekly predictions
 */
export async function fetchWeeklyPredictions() {
  return fetchJson('/api/predictions/weekly');
}

/**
 * Fetch monthly predictions
 */
export async function fetchMonthlyPredictions() {
  return fetchJson('/api/predictions/monthly');
}

/**
 * Fetch portfolio optimization
 */
export async function fetchPortfolio() {
  return fetchJson('/api/portfolio');
}

/**
 * Fetch AI predictions
 */
export async function fetchAIPredictions(top: number = 20) {
  return fetchJson(`/api/ai/predictions?top=${top}`);
}

/**
 * Fetch API health status
 */
export async function fetchHealth() {
  return fetchJson('/api/health');
}

export async function fetchAutonomousDashboard(): Promise<ApiAutonomousDashboardResponse> {
  return fetchJson<ApiAutonomousDashboardResponse>('/api/autonomous/dashboard');
}

export async function fetchAutonomousSignals(limit: number = 25): Promise<ApiAutonomousSignalCard[]> {
  return fetchJson<ApiAutonomousSignalCard[]>(`/api/autonomous/signals?limit=${limit}`);
}

export async function fetchAutonomousSignal(symbol: string): Promise<ApiAutonomousSignalCard> {
  return fetchJson<ApiAutonomousSignalCard>(`/api/autonomous/signals/${symbol}`);
}

// ─── Trading Agent ────────────────────────────────────────────────────────────

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Failed to post ${path}: ${response.statusText}`);
  }
  return response.json();
}

export interface ApiTraderPosition {
  symbol: string;
  sector: string;
  units: number;
  entry_price: number;
  entry_date: string;
  stop_loss: number;
  target_1: number;
  target_2: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  ml_confidence: number;
  status: string;
}

export interface ApiTraderStatus {
  is_running: boolean;
  mode: string;
  last_run_at: string | null;
  next_run_at: string | null;
  open_positions: ApiTraderPosition[];
  total_trades: number;
  total_realized_pnl: number;
  portfolio_value: number;
  cash_balance: number;
  peak_portfolio_value: number;
  max_drawdown_pct: number;
  win_rate: number;
  last_run_summary: Record<string, unknown> | null;
}

export interface ApiTraderRecommendation {
  rank: number;
  symbol: string;
  sector: string;
  cmp: number;
  rise_probability: number;
  action: string;
  confidence: number;
  risk_reward: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  kelly_size_pct: number;
  fcs_score: number;
  reasoning: string;
}

export async function fetchTraderStatus(): Promise<ApiTraderStatus> {
  return fetchJson<ApiTraderStatus>('/api/autonomous/trader/status');
}

export async function fetchTraderRecommendations(topN: number = 10): Promise<ApiTraderRecommendation[]> {
  return fetchJson<ApiTraderRecommendation[]>(`/api/autonomous/trader/recommendations?top_n=${topN}`);
}

export async function runTraderCycle(): Promise<{ message: string; mode: string }> {
  return postJson<{ message: string; mode: string }>('/api/autonomous/trader/run');
}

// ─── Broker (Mero Share + TMS) ───────────────────────────────────────────────

export interface ApiBrokerConnectRequest {
  mero_share_client_id?: string;
  mero_share_password?: string;
  tms_url?: string;
  tms_username?: string;
  tms_password?: string;
  tms_pin?: string;
  paper_mode: boolean;
}

export interface ApiBrokerConnectResponse {
  connected: boolean;
  mode: string;
  message: string;
}

export interface ApiBrokerHolding {
  symbol: string;
  company_name: string;
  units: number;
  ltp: number;
  wacc: number;
  unrealized_gain: number;
  unrealized_gain_pct: number;
}

export interface ApiBrokerPortfolio {
  holdings: ApiBrokerHolding[];
  total_value: number;
  total_cost: number;
  total_gain: number;
  total_gain_pct: number;
  cash_balance: number;
  fetched_at: string;
}

export interface ApiTradeRecord {
  trade_id: string;
  symbol: string;
  action: string;
  quantity: number;
  price: number;
  total_amount: number;
  status: string;
  timestamp: string;
  order_id: string | null;
  notes: string;
}

export async function connectBroker(req: ApiBrokerConnectRequest): Promise<ApiBrokerConnectResponse> {
  return postJson<ApiBrokerConnectResponse>('/api/autonomous/trader/connect', req);
}

export async function fetchTraderPortfolio(): Promise<ApiBrokerPortfolio> {
  return fetchJson<ApiBrokerPortfolio>('/api/autonomous/trader/portfolio');
}

export async function fetchTraderPositions(): Promise<ApiTraderPosition[]> {
  return fetchJson<ApiTraderPosition[]>('/api/autonomous/trader/positions');
}

export async function fetchTraderTrades(): Promise<ApiTradeRecord[]> {
  return fetchJson<ApiTradeRecord[]>('/api/autonomous/trader/trades');
}

export async function placeManualTrade(req: {
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  notes?: string;
}): Promise<ApiTradeRecord> {
  return postJson<ApiTradeRecord>('/api/autonomous/trader/manual-trade', req);
}

export async function forceExitPosition(symbol: string, reason?: string): Promise<{ message: string; success: boolean }> {
  return postJson<{ message: string; success: boolean }>('/api/autonomous/trader/exit', {
    symbol,
    reason: reason ?? 'Manual exit via UI',
  });
}

// ─── Portfolio Self-Audit ────────────────────────────────────────────────────

export interface ApiAuditHolding extends ApiBrokerHolding {
  value: number;
  weight_pct: number;
  sector: string;
  ai_action: string;
  rise_probability: number | null;
  fcs_score: number | null;
  stop_loss: number | null;
  target_1: number | null;
  ai_reasoning: string;
}

export interface ApiAuditFinding {
  severity: 'good' | 'info' | 'warning' | 'critical';
  title: string;
  detail: string;
}

export interface ApiPortfolioAudit {
  fetched_at: string;
  mode: string;
  health_score: number;
  summary: string;
  totals: { value: number; cost: number; gain: number; gain_pct: number; cash: number };
  holdings: ApiAuditHolding[];
  findings: ApiAuditFinding[];
  sector_exposure: Array<{ sector: string; value: number; weight_pct: number }>;
}

export async function fetchPortfolioAudit(): Promise<ApiPortfolioAudit> {
  return fetchJson<ApiPortfolioAudit>('/api/autonomous/trader/audit');
}
