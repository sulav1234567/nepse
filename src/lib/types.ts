// ============================================================================
// NEPSE-ALPHA ULTIMATE — Type Definitions
// ============================================================================

export type Signal = 'STRONG BUY' | 'BUY' | 'SPECULATIVE BUY' | 'HOLD' | 'AVOID' | 'SHORT ALERT';
export type Regime = 'BULL TREND' | 'BEAR TREND' | 'HIGH VOLATILITY' | 'SIDEWAYS' | 'POLITICAL RISK';
export type PredictionTier = 'DAILY' | 'WEEKLY' | 'MONTHLY';
export type SISLevel = 'QUIET' | 'WARMING UP' | 'ACTIVE' | 'HOT' | 'EXTREME FOMO';
export type BMRLevel = 'RETAIL DOMINATED' | 'MIXED' | 'INSTITUTIONAL MAJORITY' | 'INSTITUTIONAL DOMINANCE';
export type TTHStatus = 'SAFE' | 'WARNING' | 'CRITICAL';
export type PoliticalRisk = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type BSTSConfidence = 'NORMAL' | 'WIDENING' | 'RECALIBRATING';
export type RightSharePhase = 'N/A' | 'PHASE 1' | 'PHASE 2' | 'PHASE 3' | 'PHASE 4';

export type Sector =
  | 'Commercial Bank'
  | 'Development Bank'
  | 'Finance'
  | 'Hydropower'
  | 'Insurance'
  | 'Microfinance'
  | 'Manufacturing'
  | 'Hotel & Tourism'
  | 'Trading'
  | 'Others';

export interface Stock {
  symbol: string;
  name: string;
  sector: Sector;
  cmp: number;
  previousClose: number;
  change: number;
  changePercent: number;
  volume: number;
  avgVolume20d: number;
  high52w: number;
  low52w: number;
  eps: number;
  pe: number;
  pb: number;
  roe: number;
  dividendYield: number;
  bookValue: number;
  marketCap: number;
}

export interface HistoricalPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TechnicalIndicators {
  ema9: number;
  ema21: number;
  ema55: number;
  sma200: number;
  rsi14: number;
  macdLine: number;
  macdSignal: number;
  macdHistogram: number;
  stochRsi: number;
  obv: number;
  atr14: number;
  volumeRatio: number; // current vol / 20d avg vol
}

export interface EMAAlignment {
  type: 'GOLDEN' | 'MIXED' | 'DEATH';
  score: number;
}

export interface LayerScores {
  fvl: number;
  tml: number;
  ssil: number;
  gtbil: number;
  mrlll: number;
}

export interface LayerWeights {
  fvl: number;
  tml: number;
  ssil: number;
  gtbil: number;
  mrlll: number;
}

export interface OverrideCondition {
  id: string;
  name: string;
  triggered: boolean;
  description: string;
}

export interface FCSResult {
  score: number;
  signal: Signal;
  layerScores: LayerScores;
  weights: LayerWeights;
  overrides: OverrideCondition[];
  activeOverride: string | null;
}

export interface PriceTarget {
  pt1: number;
  pt2: number;
  stopLoss: number;
  trailingStopActivation: number;
}

export interface WarningFlags {
  sisScore: number;
  sisLevel: SISLevel;
  bmr: number;
  bmrLevel: BMRLevel;
  circularTrading: boolean;
  rightSharePhase: RightSharePhase;
  tthStatus: TTHStatus;
  politicalRisk: PoliticalRisk;
  bstsConfidence: BSTSConfidence;
  dataStale: boolean;
  dataStalenessMinutes: number;
}

export interface PredictionReport {
  symbol: string;
  companyName: string;
  sector: Sector;
  tier: PredictionTier;
  timestamp: string;
  regime: Regime;
  dataFreshness: 'LIVE' | 'CACHED' | 'DEMO';
  fcs: FCSResult;
  priceTargets: PriceTarget;
  cmp: number;
  bstsMeanFairValue: number;
  overvaluationPercent: number;
  timeHorizon: string;
  timingConfidence: 'HIGH' | 'MEDIUM' | 'LOW';
  recommendedAllocation: number;
  regimeMultiplier: number;
  executionMethod: string;
  keyDrivers: string[];
  warningFlags: WarningFlags;
  retailInstitutionalVerdict: string;
  invalidationConditions: string[];
  signalType: string;
}

export interface DailyPrediction {
  rank: number;
  symbol: string;
  name: string;
  signalType: string;
  entryZone: string;
  target: number;
  stopLoss: number;
  confidence: number;
  signal: Signal;
  rationale: string;
}

export interface WeeklyPrediction {
  symbol: string;
  name: string;
  entryRange: string;
  targetWeek: number;
  stopLoss: number;
  fcs: number;
  signal: Signal;
  timeHorizon: string;
  keyDriver: string;
}

export interface MonthlyPrediction {
  symbol: string;
  name: string;
  entryStrategy: string;
  target1m: number;
  target3m: number;
  stopLoss: number;
  portfolioWeight: number;
  signal: Signal;
  thesis: string;
  catalystCalendar: string;
  invalidationConditions: string[];
}

export interface MarketOverview {
  nepseIndex: number;
  nepseChange: number;
  nepseChangePercent: number;
  totalTurnover: number;
  totalVolume: number;
  totalTransactions: number;
  advancers: number;
  decliners: number;
  unchanged: number;
  regime: Regime;
  regimeConfidence: number;
  interbankRate: number;
  tBillYield: number;
}

export interface SectorPerformance {
  sector: Sector;
  index: number;
  change: number;
  changePercent: number;
  volume: number;
}

export interface AuditResult {
  date: string;
  predictionsMade: number;
  hitRate: number;
  avgReturnOnHits: number;
  avgLossOnStops: number;
  sortinoRatio: number;
  strongestSignal: { symbol: string; description: string };
  weakestSignal: { symbol: string; description: string };
  layerWeights: LayerWeights;
}

export interface RegimeDetection {
  regime: Regime;
  confidence: number;
  weights: LayerWeights;
  positionMultiplier: number;
  cashBuffer: number;
  description: string;
  bestSignals: string[];
}
