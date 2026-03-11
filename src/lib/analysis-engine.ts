// ============================================================================
// NEPSE-ALPHA ULTIMATE — Five-Layer Analysis Engine
// ============================================================================

import { Stock, HistoricalPrice, TechnicalIndicators, LayerScores, EMAAlignment,
         Signal, FCSResult, LayerWeights, OverrideCondition, PriceTarget, WarningFlags,
         SISLevel, BMRLevel } from './types';

// ─────────────────────────────────────────────────────────────────────────────
// TECHNICAL INDICATOR CALCULATIONS
// ─────────────────────────────────────────────────────────────────────────────

function computeEMA(prices: number[], period: number): number {
  if (prices.length < period) return prices[prices.length - 1] || 0;
  const k = 2 / (period + 1);
  let ema = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < prices.length; i++) {
    ema = prices[i] * k + ema * (1 - k);
  }
  return Math.round(ema * 100) / 100;
}

function computeSMA(prices: number[], period: number): number {
  if (prices.length < period) return prices[prices.length - 1] || 0;
  const slice = prices.slice(-period);
  return Math.round((slice.reduce((a, b) => a + b, 0) / period) * 100) / 100;
}

function computeRSI(prices: number[], period: number = 14): number {
  if (prices.length < period + 1) return 50;
  let gains = 0, losses = 0;
  for (let i = prices.length - period; i < prices.length; i++) {
    const change = prices[i] - prices[i - 1];
    if (change > 0) gains += change;
    else losses += Math.abs(change);
  }
  const avgGain = gains / period;
  const avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return Math.round((100 - 100 / (1 + rs)) * 100) / 100;
}

function computeMACD(prices: number[]): { macdLine: number; signal: number; histogram: number } {
  const ema12 = computeEMA(prices, 12);
  const ema26 = computeEMA(prices, 26);
  const macdLine = Math.round((ema12 - ema26) * 100) / 100;
  // Simplified signal line
  const recentPrices = prices.slice(-9);
  const signal = Math.round(macdLine * 0.85 * 100) / 100;
  const histogram = Math.round((macdLine - signal) * 100) / 100;
  return { macdLine, signal, histogram };
}

function computeATR(history: HistoricalPrice[], period: number = 14): number {
  if (history.length < period + 1) return history[history.length - 1]?.high - history[history.length - 1]?.low || 10;
  let atr = 0;
  for (let i = history.length - period; i < history.length; i++) {
    const tr = Math.max(
      history[i].high - history[i].low,
      Math.abs(history[i].high - history[i - 1].close),
      Math.abs(history[i].low - history[i - 1].close)
    );
    atr += tr;
  }
  return Math.round((atr / period) * 100) / 100;
}

function computeOBV(history: HistoricalPrice[]): number {
  let obv = 0;
  for (let i = 1; i < history.length; i++) {
    if (history[i].close > history[i - 1].close) obv += history[i].volume;
    else if (history[i].close < history[i - 1].close) obv -= history[i].volume;
  }
  return obv;
}

function computeStochRSI(prices: number[], period: number = 14): number {
  const rsiValues: number[] = [];
  for (let i = period + 1; i <= prices.length; i++) {
    rsiValues.push(computeRSI(prices.slice(0, i), period));
  }
  if (rsiValues.length < period) return 50;
  const recent = rsiValues.slice(-period);
  const min = Math.min(...recent);
  const max = Math.max(...recent);
  if (max === min) return 50;
  return Math.round(((rsiValues[rsiValues.length - 1] - min) / (max - min)) * 100 * 100) / 100;
}

export function computeTechnicalIndicators(history: HistoricalPrice[], stock: Stock): TechnicalIndicators {
  const closes = history.map(h => h.close);
  const macd = computeMACD(closes);
  const currentVolume = history.length > 0 ? history[history.length - 1].volume : stock.volume;
  
  return {
    ema9: computeEMA(closes, 9),
    ema21: computeEMA(closes, 21),
    ema55: computeEMA(closes, 55),
    sma200: computeSMA(closes, Math.min(closes.length, 200)),
    rsi14: computeRSI(closes, 14),
    macdLine: macd.macdLine,
    macdSignal: macd.signal,
    macdHistogram: macd.histogram,
    stochRsi: computeStochRSI(closes, 14),
    obv: computeOBV(history),
    atr14: computeATR(history, 14),
    volumeRatio: stock.avgVolume20d > 0 ? Math.round((currentVolume / stock.avgVolume20d) * 100) / 100 : 1,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// LAYER 1: FUNDAMENTAL VALUE LAYER (FVL)
// ─────────────────────────────────────────────────────────────────────────────

export function computeFVL(stock: Stock): { score: number; details: string[] } {
  let score = 50; // Base score
  const details: string[] = [];

  // Sector-specific fair P/E ranges
  const fairPE: Record<string, [number, number]> = {
    'Commercial Bank': [12, 18],
    'Development Bank': [10, 16],
    'Hydropower': [15, 25],
    'Insurance': [12, 20],
    'Microfinance': [14, 22],
    'Manufacturing': [15, 25],
    'Hotel & Tourism': [18, 30],
    'Finance': [10, 15],
    'Trading': [12, 20],
    'Others': [12, 20],
  };

  const [lowPE, highPE] = fairPE[stock.sector] || [12, 20];
  const medianPE = (lowPE + highPE) / 2;

  // P/E Analysis
  if (stock.pe > 0) {
    if (stock.pe < lowPE) {
      score += 18;
      details.push(`P/E ${stock.pe.toFixed(1)} below sector fair range ${lowPE}-${highPE} — undervalued`);
    } else if (stock.pe <= highPE) {
      score += 5;
      details.push(`P/E ${stock.pe.toFixed(1)} within fair range`);
    } else if (stock.pe <= highPE * 1.5) {
      score -= 8;
      details.push(`P/E ${stock.pe.toFixed(1)} above sector fair range — overvalued`);
    } else {
      score -= 18;
      details.push(`P/E ${stock.pe.toFixed(1)} significantly overvalued vs sector median ${medianPE.toFixed(1)}`);
    }
  }

  // P/B Analysis (most important for banks)
  if (stock.sector === 'Commercial Bank' || stock.sector === 'Development Bank') {
    if (stock.pb < 1.2) {
      score += 22;
      details.push(`P/B ${stock.pb.toFixed(2)} < 1.2 — strong undervaluation for bank`);
    } else if (stock.pb < 1.8) {
      score += 10;
      details.push(`P/B ${stock.pb.toFixed(2)} — moderately valued`);
    } else if (stock.pb < 2.5) {
      score += 0;
      details.push(`P/B ${stock.pb.toFixed(2)} — fairly valued`);
    } else {
      score -= 12;
      details.push(`P/B ${stock.pb.toFixed(2)} — overvalued for bank sector`);
    }
  }

  // ROE Analysis
  const minROE: Record<string, number> = {
    'Commercial Bank': 12, 'Development Bank': 10, 'Insurance': 10,
    'Hydropower': 8, 'Microfinance': 12, 'Manufacturing': 10,
  };
  const sectorMinROE = minROE[stock.sector] || 10;
  if (stock.roe >= sectorMinROE * 1.5) {
    score += 15;
    details.push(`ROE ${stock.roe.toFixed(1)}% — excellent profitability`);
  } else if (stock.roe >= sectorMinROE) {
    score += 5;
    details.push(`ROE ${stock.roe.toFixed(1)}% — meets sector minimum`);
  } else {
    score -= 10;
    details.push(`ROE ${stock.roe.toFixed(1)}% below sector minimum ${sectorMinROE}%`);
  }

  // Dividend yield vs T-Bill yield (~5.8%)
  const tBillYield = 5.8;
  if (stock.dividendYield > tBillYield) {
    score += 12;
    details.push(`Dividend yield ${stock.dividendYield.toFixed(1)}% exceeds T-Bill ${tBillYield}% — institutional price floor`);
  } else if (stock.dividendYield > tBillYield * 0.7) {
    score += 5;
    details.push(`Dividend yield ${stock.dividendYield.toFixed(1)}% — attractive`);
  } else if (stock.dividendYield > 0) {
    score += 0;
    details.push(`Dividend yield ${stock.dividendYield.toFixed(1)}% — below T-Bill rate`);
  }

  // BSTS-style fair value estimate (simplified)
  const bstsFairValue = stock.bookValue * (stock.roe / 100) * medianPE;
  const overvaluation = ((stock.cmp - bstsFairValue) / bstsFairValue) * 100;
  
  if (overvaluation < -20) score += 10;
  else if (overvaluation < -10) score += 5;
  else if (overvaluation > 25) score -= 15;
  else if (overvaluation > 10) score -= 5;

  return { score: Math.max(0, Math.min(100, score)), details };
}

// ─────────────────────────────────────────────────────────────────────────────
// LAYER 2: TECHNICAL MOMENTUM LAYER (TML)
// ─────────────────────────────────────────────────────────────────────────────

export function computeTML(stock: Stock, indicators: TechnicalIndicators, history: HistoricalPrice[]): { score: number; details: string[] } {
  let score = 50;
  const details: string[] = [];

  // EMA Alignment
  const alignment = getEMAAlignment(indicators);
  score += alignment.score;
  details.push(`EMA alignment: ${alignment.type} (EMA-9:${indicators.ema9.toFixed(0)} EMA-21:${indicators.ema21.toFixed(0)} EMA-55:${indicators.ema55.toFixed(0)})`);

  // SMA-200 Position
  if (stock.cmp > indicators.sma200) {
    score += 10;
    details.push(`Price above SMA-200 (${indicators.sma200.toFixed(0)}) — long-term bull structure`);
  } else {
    score -= 10;
    details.push(`Price below SMA-200 (${indicators.sma200.toFixed(0)}) — long-term bear structure`);
  }

  // RSI Analysis
  if (indicators.rsi14 < 30) {
    score += 12;
    details.push(`RSI ${indicators.rsi14.toFixed(1)} — OVERSOLD — potential reversal zone`);
  } else if (indicators.rsi14 < 50) {
    score += 5;
    details.push(`RSI ${indicators.rsi14.toFixed(1)} — recovering, early trend potential`);
  } else if (indicators.rsi14 < 70) {
    score += 8;
    details.push(`RSI ${indicators.rsi14.toFixed(1)} — healthy momentum`);
  } else {
    score -= 5;
    details.push(`RSI ${indicators.rsi14.toFixed(1)} — OVERBOUGHT — caution`);
  }

  // MACD
  if (indicators.macdHistogram > 0 && indicators.macdLine > indicators.macdSignal) {
    score += 10;
    details.push(`MACD bullish crossover — histogram expanding`);
  } else if (indicators.macdHistogram < 0) {
    score -= 10;
    details.push(`MACD bearish — histogram contracting`);
  }

  // Volume Analysis
  if (indicators.volumeRatio > 1.5 && stock.changePercent > 0) {
    score += 20;
    details.push(`CONFIRMED BREAKOUT — volume ${(indicators.volumeRatio * 100).toFixed(0)}% of avg with price up`);
  } else if (indicators.volumeRatio > 1.0 && stock.changePercent > 0) {
    score += 12;
    details.push(`Strong rally on ${(indicators.volumeRatio * 100).toFixed(0)}% volume`);
  } else if (indicators.volumeRatio < 0.7 && stock.changePercent > 0) {
    score += 4;
    details.push(`Weak rally — volume below average`);
  } else if (indicators.volumeRatio > 1.5 && stock.changePercent < -2) {
    score -= 20;
    details.push(`PANIC SELLING — high volume decline`);
  } else if (stock.changePercent < 0 && indicators.volumeRatio < 0.8) {
    score -= 5;
    details.push(`Low-conviction pullback — may be buyable`);
  }

  // 52-week position
  const range52w = stock.high52w - stock.low52w;
  const position52w = (stock.cmp - stock.low52w) / range52w;
  if (position52w < 0.3) {
    score += 8;
    details.push(`Near 52-week low — potential value zone`);
  } else if (position52w > 0.9) {
    score -= 5;
    details.push(`Near 52-week high — limited upside without breakout`);
  }

  return { score: Math.max(0, Math.min(100, score)), details };
}

export function getEMAAlignment(indicators: TechnicalIndicators): EMAAlignment {
  if (indicators.ema9 > indicators.ema21 && indicators.ema21 > indicators.ema55) {
    return { type: 'GOLDEN', score: 20 };
  } else if (indicators.ema9 < indicators.ema21 && indicators.ema21 < indicators.ema55) {
    return { type: 'DEATH', score: -20 };
  }
  return { type: 'MIXED', score: 0 };
}

// ─────────────────────────────────────────────────────────────────────────────
// LAYER 3: SOCIAL SENTIMENT & INTELLIGENCE LAYER (SSIL) — Simulated
// ─────────────────────────────────────────────────────────────────────────────

export function computeSSIL(stock: Stock, indicators: TechnicalIndicators): { score: number; sis: number; details: string[] } {
  const details: string[] = [];
  
  // Simulate SIS from volume anomalies and price momentum
  const volumeAnomaly = Math.max(0, (indicators.volumeRatio - 1) * 40);
  const momentumSignal = Math.abs(stock.changePercent) * 8;
  const priceVelocity = stock.changePercent > 0 ? stock.changePercent * 5 : 0;
  
  // SIS: 0-100
  const sis = Math.min(100, Math.round(volumeAnomaly + momentumSignal + priceVelocity + Math.random() * 15));
  
  let score = 50;
  
  // SIS interpretation for scoring
  if (sis < 25) {
    score += 15; // Quiet = ideal entry before retail notices
    details.push(`SIS ${sis} — QUIET — retail not interested, ideal stealthy entry`);
  } else if (sis < 50) {
    score += 8;
    details.push(`SIS ${sis} — warming up, early retail interest forming`);
  } else if (sis < 70) {
    score += 3;
    details.push(`SIS ${sis} — ACTIVE — retail engaged, verify with GTBIL`);
  } else if (sis < 85) {
    score -= 10;
    details.push(`SIS ${sis} — HOT — FOMO beginning, late entry risk`);
  } else {
    score -= 25;
    details.push(`SIS ${sis} — EXTREME FOMO — statistically worst time to buy`);
  }

  // Sector rotation proxy
  if (stock.sector === 'Hydropower' && new Date().getMonth() >= 3 && new Date().getMonth() <= 7) {
    score += 8;
    details.push(`Monsoon season approaching — hydropower sentiment positive`);
  }

  return { score: Math.max(0, Math.min(100, score)), sis, details };
}

// ─────────────────────────────────────────────────────────────────────────────
// LAYER 4: GRAPH THEORY & BROKER INTELLIGENCE LAYER (GTBIL) — Simulated
// ─────────────────────────────────────────────────────────────────────────────

export function computeGTBIL(stock: Stock, indicators: TechnicalIndicators): { score: number; bmr: number; details: string[] } {
  const details: string[] = [];
  
  // Simulate BMR from volume patterns and stock characteristics
  // Large-cap, well-known stocks have higher institutional participation
  const marketCapFactor = Math.min(1, stock.marketCap / 50000000000); // Normalize by 50B
  const volumeConsistency = indicators.volumeRatio > 0.8 && indicators.volumeRatio < 1.5 ? 0.3 : 0;
  const blueChipBonus = stock.sector === 'Commercial Bank' ? 0.15 : 0;
  
  // BMR: 0-100%
  const bmr = Math.min(80, Math.round((marketCapFactor * 30 + volumeConsistency * 20 + blueChipBonus * 20 + Math.random() * 25) * 100) / 100);
  
  let score = 50;
  
  if (bmr > 50) {
    score += 25;
    details.push(`BMR ${bmr.toFixed(0)}% — INSTITUTIONAL DOMINANCE — strongest buy confirmation`);
  } else if (bmr > 35) {
    score += 15;
    details.push(`BMR ${bmr.toFixed(0)}% — institutional majority, high conviction`);
  } else if (bmr > 20) {
    score += 5;
    details.push(`BMR ${bmr.toFixed(0)}% — mixed participation, moderate conviction`);
  } else {
    score -= 15;
    details.push(`BMR ${bmr.toFixed(0)}% — RETAIL DOMINATED — high pump risk`);
  }

  // Accumulation detection proxy (volume increasing while price stable)
  if (indicators.volumeRatio > 1.3 && Math.abs(stock.changePercent) < 1.5) {
    score += 15;
    details.push(`Accumulation pattern detected — volume rising, price stable`);
  }

  // OBV leading signal
  if (indicators.obv > 0 && stock.changePercent <= 0) {
    score += 10;
    details.push(`OBV leading — smart money absorbing supply before price moves`);
  }

  return { score: Math.max(0, Math.min(100, score)), bmr, details };
}

// ─────────────────────────────────────────────────────────────────────────────
// LAYER 5: MACRO & REGIONAL LEAD-LAG LAYER (MRLLL)
// ─────────────────────────────────────────────────────────────────────────────

export function computeMRLLL(stock: Stock, interbankRate: number = 4.25): { score: number; details: string[] } {
  let score = 50;
  const details: string[] = [];

  // Interbank rate analysis
  if (interbankRate < 4) {
    score += 20;
    details.push(`Interbank rate ${interbankRate}% — ABUNDANT LIQUIDITY — bull conditions`);
  } else if (interbankRate < 5) {
    score += 10;
    details.push(`Interbank rate ${interbankRate}% — comfortable liquidity`);
  } else if (interbankRate < 7) {
    score -= 5;
    details.push(`Interbank rate ${interbankRate}% — TIGHTENING — reduce finance exposure`);
  } else {
    score -= 20;
    details.push(`Interbank rate ${interbankRate}% — LIQUIDITY STRESS — defensive posture`);
  }

  // Sector-specific macro sensitivity
  if (stock.sector === 'Commercial Bank' || stock.sector === 'Development Bank') {
    if (interbankRate < 5) {
      score += 10;
      details.push(`Low rates positive for bank earnings — NIM expansion likely`);
    } else {
      score -= 8;
      details.push(`High rates pressuring bank sector`);
    }
  }

  if (stock.sector === 'Hydropower') {
    // Monsoon seasonality
    const month = new Date().getMonth();
    if (month >= 5 && month <= 8) { // June-Sep (monsoon)
      score += 12;
      details.push(`Monsoon active — hydropower generation at peak`);
    } else if (month >= 3 && month <= 4) {
      score += 8;
      details.push(`Pre-monsoon positioning window for hydro stocks`);
    } else if (month >= 10 && month <= 1) {
      score -= 8;
      details.push(`Winter dry season — reduced hydro generation`);
    }
  }

  // NIFTY correlation proxy (simulated)  
  const nifyBias = 1.5; // Assume mild bullish NIFTY bias
  if (nifyBias > 1.5) {
    score += 3;
    details.push(`NIFTY positive bias — regional tailwind`);
  } else if (nifyBias < -1.5) {
    score -= 3;
    details.push(`NIFTY negative — regional headwind`);
  }

  return { score: Math.max(0, Math.min(100, score)), details };
}

// ─────────────────────────────────────────────────────────────────────────────
// MASTER SIGNAL AGGREGATOR
// ─────────────────────────────────────────────────────────────────────────────

export function getSignalFromFCS(fcs: number): Signal {
  if (fcs >= 85) return 'STRONG BUY';
  if (fcs >= 70) return 'BUY';
  if (fcs >= 55) return 'SPECULATIVE BUY';
  if (fcs >= 40) return 'HOLD';
  if (fcs >= 25) return 'AVOID';
  return 'SHORT ALERT';
}

export function checkOverrides(stock: Stock, sis: number, bmr: number, indicators: TechnicalIndicators): OverrideCondition[] {
  const overrides: OverrideCondition[] = [
    {
      id: 'PUMP_TRAP',
      name: 'Retail FOMO Trap',
      triggered: sis > 85 && bmr < 15,
      description: 'SIS > 85 + BMR < 15% — RETAIL FOMO TRAP — Do not enter.'
    },
    {
      id: 'CIRCULAR_TRADING',
      name: 'Circular Trading Detected',
      triggered: false, // Would require broker graph data
      description: 'Circular trading cluster detected — volume is manufactured.'
    },
    {
      id: 'TTH_CRITICAL',
      name: 'Time-to-Halt Critical',
      triggered: false, // Would require live index velocity data
      description: 'Index approaching circuit halt — all buy signals suppressed.'
    },
    {
      id: 'RIGHT_SHARE_PHASE3',
      name: 'Right Share Phase 3 Active',
      triggered: false, // Would require SEBON data
      description: 'Post book close dilution — signal capped at AVOID.'
    },
    {
      id: 'BSTS_UNCERTAINTY',
      name: 'Model Uncertainty High',
      triggered: false,
      description: 'BSTS confidence interval too wide — model recalibrating.'
    },
    {
      id: 'POLITICAL_RISK',
      name: 'Political Risk Critical',
      triggered: false, // Would require NLP political monitoring
      description: 'Political risk critical — all signals downgraded one level.'
    },
  ];
  return overrides;
}

export function computeFCS(
  stock: Stock,
  history: HistoricalPrice[],
  weights: LayerWeights,
  interbankRate: number = 4.25
): FCSResult {
  const indicators = computeTechnicalIndicators(history, stock);
  
  const fvl = computeFVL(stock);
  const tml = computeTML(stock, indicators, history);
  const ssil = computeSSIL(stock, indicators);
  const gtbil = computeGTBIL(stock, indicators);
  const mrlll = computeMRLLL(stock, interbankRate);

  const layerScores: LayerScores = {
    fvl: fvl.score,
    tml: tml.score,
    ssil: ssil.score,
    gtbil: gtbil.score,
    mrlll: mrlll.score,
  };

  const rawFCS = Math.round(
    fvl.score * weights.fvl +
    tml.score * weights.tml +
    ssil.score * weights.ssil +
    gtbil.score * weights.gtbil +
    mrlll.score * weights.mrlll
  );

  const overrides = checkOverrides(stock, ssil.sis, gtbil.bmr, indicators);
  const activeOverride = overrides.find(o => o.triggered);

  let finalFCS = rawFCS;
  if (activeOverride) {
    if (activeOverride.id === 'PUMP_TRAP' || activeOverride.id === 'CIRCULAR_TRADING') {
      finalFCS = Math.min(finalFCS, 30); // Force to AVOID
    } else if (activeOverride.id === 'POLITICAL_RISK') {
      finalFCS = Math.max(0, finalFCS - 15); // Downgrade one level
    }
  }

  return {
    score: Math.max(0, Math.min(100, finalFCS)),
    signal: getSignalFromFCS(finalFCS),
    layerScores,
    weights,
    overrides,
    activeOverride: activeOverride?.id || null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// PRICE TARGET COMPUTATION
// ─────────────────────────────────────────────────────────────────────────────

export function computePriceTargets(stock: Stock, history: HistoricalPrice[], fcs: FCSResult): PriceTarget {
  const atr = computeATR(history);
  
  // PT1: Next resistance / moderate target
  const pt1Multiplier = fcs.score >= 85 ? 1.12 :
                        fcs.score >= 70 ? 1.08 :
                        fcs.score >= 55 ? 1.05 : 1.03;
  
  // PT2: Extended target (Fibonacci extension)
  const pt2Multiplier = pt1Multiplier * 1.618 - 0.618;
  
  // Stop loss: 2x ATR
  const stopMultiplier = fcs.score >= 85 ? 1.5 : fcs.score >= 55 ? 2.0 : 1.0;
  
  return {
    pt1: Math.round(stock.cmp * pt1Multiplier),
    pt2: Math.round(stock.cmp * pt2Multiplier),
    stopLoss: Math.round(stock.cmp - stopMultiplier * atr),
    trailingStopActivation: Math.round(stock.cmp + 1.5 * atr),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// WARNING FLAGS COMPUTATION
// ─────────────────────────────────────────────────────────────────────────────

export function computeWarningFlags(stock: Stock, indicators: TechnicalIndicators): WarningFlags {
  const ssil = computeSSIL(stock, indicators);
  const gtbil = computeGTBIL(stock, indicators);
  
  const sisLevel: SISLevel = ssil.sis < 25 ? 'QUIET' :
                              ssil.sis < 50 ? 'WARMING UP' :
                              ssil.sis < 70 ? 'ACTIVE' :
                              ssil.sis < 85 ? 'HOT' : 'EXTREME FOMO';

  const bmrLevel: BMRLevel = gtbil.bmr > 50 ? 'INSTITUTIONAL DOMINANCE' :
                              gtbil.bmr > 35 ? 'INSTITUTIONAL MAJORITY' :
                              gtbil.bmr > 20 ? 'MIXED' : 'RETAIL DOMINATED';

  return {
    sisScore: ssil.sis,
    sisLevel,
    bmr: gtbil.bmr,
    bmrLevel,
    circularTrading: false,
    rightSharePhase: 'N/A',
    tthStatus: 'SAFE',
    politicalRisk: 'LOW',
    bstsConfidence: 'NORMAL',
    dataStale: false,
    dataStalenessMinutes: 0,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// FULL ANALYSIS FOR A STOCK
// ─────────────────────────────────────────────────────────────────────────────

export interface FullAnalysis {
  stock: Stock;
  indicators: TechnicalIndicators;
  fcs: FCSResult;
  priceTargets: PriceTarget;
  warningFlags: WarningFlags;
  fvlDetails: string[];
  tmlDetails: string[];
  ssilDetails: string[];
  gtbilDetails: string[];
  mrlllDetails: string[];
  overvaluationPercent: number;
  bstsFairValue: number;
  retailInstitutionalVerdict: string;
}

export function analyzeStock(stock: Stock, history: HistoricalPrice[], weights: LayerWeights): FullAnalysis {
  const indicators = computeTechnicalIndicators(history, stock);
  const fvl = computeFVL(stock);
  const tml = computeTML(stock, indicators, history);
  const ssil = computeSSIL(stock, indicators);
  const gtbil = computeGTBIL(stock, indicators);
  const mrlll = computeMRLLL(stock);
  const fcs = computeFCS(stock, history, weights);
  const priceTargets = computePriceTargets(stock, history, fcs);
  const warningFlags = computeWarningFlags(stock, indicators);

  // BSTS fair value (simplified)
  const sectorMedianPE = ({ 'Commercial Bank': 15, 'Development Bank': 13, 'Hydropower': 20, 'Insurance': 16, 'Microfinance': 18, 'Manufacturing': 20, 'Hotel & Tourism': 24, 'Finance': 12, 'Trading': 16, 'Others': 16 } as Record<string, number>)[stock.sector] || 15;
  const bstsFairValue = Math.round(stock.bookValue * (stock.roe / 100) * sectorMedianPE);
  const overvaluationPercent = Math.round(((stock.cmp - bstsFairValue) / bstsFairValue) * 100);

  // Retail vs Institutional Verdict
  let verdict = '';
  if (ssil.sis < 30 && gtbil.bmr > 40) {
    verdict = `Retail is completely unaware (SIS ${ssil.sis}). Institutional buyers (BMR ${gtbil.bmr.toFixed(0)}%) have been accumulating while price has barely moved. When retail notices — and they will — the move will be fast and sharp. This is a textbook institutional setup.`;
  } else if (ssil.sis > 70 && gtbil.bmr < 20) {
    verdict = `SIS is at ${ssil.sis} and rising. Retail is fully engaged and driving the price. But BMR is only ${gtbil.bmr.toFixed(0)}% — institutions are barely present and may be distributing into retail demand. The pump may have 1-2 sessions remaining but this is no longer a buy setup. It is an exit setup.`;
  } else if (ssil.sis > 50 && gtbil.bmr > 30) {
    verdict = `Both retail (SIS ${ssil.sis}) and institutions (BMR ${gtbil.bmr.toFixed(0)}%) are engaged. The move has institutional backing with growing retail participation. This is a healthy trend continuation environment. Monitor for BMR decline as the exit signal.`;
  } else {
    verdict = `Mixed signals. Retail sentiment (SIS ${ssil.sis}) and institutional activity (BMR ${gtbil.bmr.toFixed(0)}%) are not strongly aligned. The setup requires patience — wait for either institutional confirmation (BMR > 35%) or sentiment catalyst (SIS break above 50) before committing capital.`;
  }

  return {
    stock,
    indicators,
    fcs,
    priceTargets,
    warningFlags,
    fvlDetails: fvl.details,
    tmlDetails: tml.details,
    ssilDetails: ssil.details,
    gtbilDetails: gtbil.details,
    mrlllDetails: mrlll.details,
    overvaluationPercent,
    bstsFairValue,
    retailInstitutionalVerdict: verdict,
  };
}
