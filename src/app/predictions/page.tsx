'use client';

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { DEMO_STOCKS, generateHistoricalPrices } from '@/lib/demo-data';
import { computeFCS, computePriceTargets, computeTechnicalIndicators, analyzeStock } from '@/lib/analysis-engine';
import { LayerWeights, Stock } from '@/lib/types';

const DAILY_WEIGHTS: LayerWeights = { fvl: 0.10, tml: 0.40, ssil: 0.25, gtbil: 0.20, mrlll: 0.05 };
const WEEKLY_WEIGHTS: LayerWeights = { fvl: 0.20, tml: 0.30, ssil: 0.20, gtbil: 0.25, mrlll: 0.05 };
const MONTHLY_WEIGHTS: LayerWeights = { fvl: 0.35, tml: 0.20, ssil: 0.10, gtbil: 0.25, mrlll: 0.10 };

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

function classifyDailySignal(stock: Stock, analysis: any): string {
  const ind = analysis.indicators;
  if (ind.volumeRatio > 2.0) return 'D1 — Pre-Open Volume Spike';
  if (stock.changePercent > 2 && ind.volumeRatio > 1.5) return 'D2 — Gap + Volume Breakout';
  if (stock.changePercent < -3 && ind.rsi14 < 35) return 'D3 — Oversold Bounce';
  if (stock.changePercent > 8) return 'D4 — Circuit Momentum';
  if (ind.volumeRatio > 1.3 && ind.rsi14 > 50) return 'D5 — Social Front-Run';
  return 'D2 — Momentum Entry';
}

function classifyWeeklySignal(stock: Stock, analysis: any): string {
  const ind = analysis.indicators;
  if (ind.volumeRatio > 1.3 && Math.abs(stock.changePercent) < 1.5) return 'W1 — Institutional Accumulation';
  if (ind.ema9 > ind.ema21 && ind.ema21 > ind.ema55) return 'W2 — EMA Golden Cross';
  if (stock.dividendYield > 5) return 'W4 — Pre-Book-Close Dividend';
  return 'W5 — Sector Rotation';
}

function classifyMonthlySignal(stock: Stock, fcs: any): string {
  if (fcs.layerScores.fvl > 80) return 'M1 — Deep Value + Catalyst';
  if (fcs.layerScores.gtbil > 70) return 'M2 — Institutional Accumulation';
  if (stock.sector === 'Commercial Bank') return 'M3 — Macro Regime Change';
  if (stock.sector === 'Hydropower') return 'M4 — Monsoon Seasonal Alpha';
  return 'M5 — Post-Correction Recovery';
}

export default function PredictionsPage() {
  const [tab, setTab] = useState<'daily' | 'weekly' | 'monthly'>('daily');
  const [predictions, setPredictions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const weights = tab === 'daily' ? DAILY_WEIGHTS : tab === 'weekly' ? WEEKLY_WEIGHTS : MONTHLY_WEIGHTS;
    const results = DEMO_STOCKS.map(stock => {
      const history = generateHistoricalPrices(stock);
      const analysis = analyzeStock(stock, history, weights);
      const fcs = analysis.fcs;
      const targets = analysis.priceTargets;
      const signalType = tab === 'daily'
        ? classifyDailySignal(stock, analysis)
        : tab === 'weekly'
        ? classifyWeeklySignal(stock, analysis)
        : classifyMonthlySignal(stock, fcs);

      return {
        stock,
        fcs: fcs.score,
        signal: fcs.signal,
        signalType,
        targets,
        fvl: fcs.layerScores.fvl,
        tml: fcs.layerScores.tml,
        ssil: fcs.layerScores.ssil,
        gtbil: fcs.layerScores.gtbil,
        mrlll: fcs.layerScores.mrlll,
        verdict: analysis.retailInstitutionalVerdict,
      };
    });
    results.sort((a, b) => b.fcs - a.fcs);
    const limit = tab === 'daily' ? 5 : tab === 'weekly' ? 10 : 5;
    setPredictions(results.filter(r => r.fcs >= 45).slice(0, limit));
    setLoading(false);
  }, [tab]);

  const tierLabel = tab === 'daily' ? 'Top 5 Daily Trades (1-5 Sessions)' : tab === 'weekly' ? 'Top 10 Weekly Positions (5-15 Sessions)' : 'Top 5 Monthly Conviction Picks (15-60 Sessions)';

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Predictions</h2>
          <div className="subtitle">Three-tier prediction engine · Daily | Weekly | Monthly</div>
          <div className="data-badge demo"><span className="pulse"></span>DEMO DATA · Engine: numpy, scipy, filterpy, scikit-learn</div>
        </div>

        <div className="tabs">
          <button className={`tab-btn ${tab === 'daily' ? 'active' : ''}`} onClick={() => setTab('daily')}>Daily</button>
          <button className={`tab-btn ${tab === 'weekly' ? 'active' : ''}`} onClick={() => setTab('weekly')}>Weekly</button>
          <button className={`tab-btn ${tab === 'monthly' ? 'active' : ''}`} onClick={() => setTab('monthly')}>Monthly</button>
        </div>

        <div style={{ marginBottom: 16, fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
          {tierLabel}
        </div>

        {loading ? (
          <div className="predictions-grid">
            {[1,2,3].map(i => <div key={i} className="loading-skeleton" style={{ height: 240, borderRadius: 16 }} />)}
          </div>
        ) : (
          <div className="predictions-grid">
            {predictions.map((p, i) => (
              <div key={p.stock.symbol} className={`prediction-card ${getSignalClass(p.signal)}`}>
                <div className="rank-badge">{i + 1}</div>
                <div className="pred-header">
                  <div>
                    <div className="pred-symbol">{p.stock.symbol}</div>
                    <div className="pred-name">{p.stock.name}</div>
                    <div className="pred-signal-type">{p.signalType}</div>
                  </div>
                </div>
                <div style={{ margin: '10px 0' }}>
                  <span className={`signal-badge ${getSignalClass(p.signal)}`}>{p.signal}</span>
                  <span style={{ marginLeft: 8, fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: '1rem', color: p.fcs >= 70 ? 'var(--bullish)' : p.fcs >= 50 ? 'var(--hold)' : 'var(--bearish)' }}>
                    FCS {Math.round(p.fcs)}
                  </span>
                </div>

                <div className="pred-metrics">
                  <div className="pred-metric">
                    <div className="pred-metric-label">CMP</div>
                    <div className="pred-metric-value">₹{p.stock.cmp.toLocaleString()}</div>
                  </div>
                  <div className="pred-metric">
                    <div className="pred-metric-label">Target</div>
                    <div className="pred-metric-value target">₹{p.targets.pt1.toLocaleString()}</div>
                  </div>
                  <div className="pred-metric">
                    <div className="pred-metric-label">Stop Loss</div>
                    <div className="pred-metric-value stop">₹{p.targets.stopLoss.toLocaleString()}</div>
                  </div>
                </div>

                {/* Layer mini-bars */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 4, margin: '12px 0' }}>
                  {[
                    { l: 'FVL', v: p.fvl, c: '#6366f1' },
                    { l: 'TML', v: p.tml, c: '#06b6d4' },
                    { l: 'SSIL', v: p.ssil, c: '#f59e0b' },
                    { l: 'GTBIL', v: p.gtbil, c: '#10b981' },
                    { l: 'MRLLL', v: p.mrlll, c: '#8b5cf6' },
                  ].map(x => (
                    <div key={x.l} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', letterSpacing: '0.05em', fontWeight: 600 }}>{x.l}</div>
                      <div style={{ height: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 2, marginTop: 3, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${x.v}%`, background: x.c, borderRadius: 2 }} />
                      </div>
                      <div style={{ fontSize: '0.65rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, marginTop: 2, color: x.v >= 65 ? 'var(--bullish)' : x.v >= 45 ? 'var(--text-secondary)' : 'var(--bearish)' }}>{Math.round(x.v)}</div>
                    </div>
                  ))}
                </div>

                <div className="pred-rationale">{p.verdict}</div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
