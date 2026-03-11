'use client';

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { DEMO_STOCKS, DEMO_MARKET_OVERVIEW, DEMO_SECTOR_PERFORMANCE, generateHistoricalPrices } from '@/lib/demo-data';
import { computeFCS, computeTechnicalIndicators, computeFVL, computeSSIL, computeGTBIL } from '@/lib/analysis-engine';
import { LayerWeights, Stock, DailyPrediction } from '@/lib/types';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts';

const DEFAULT_WEIGHTS: LayerWeights = { fvl: 0.25, tml: 0.25, ssil: 0.15, gtbil: 0.25, mrlll: 0.10 };

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

interface AnalyzedStock {
  stock: Stock;
  fcs: number;
  signal: string;
  fvl: number;
  tml: number;
  ssil: number;
  gtbil: number;
  mrlll: number;
}

export default function DashboardPage() {
  const [analyzed, setAnalyzed] = useState<AnalyzedStock[]>([]);
  const [loading, setLoading] = useState(true);
  const market = DEMO_MARKET_OVERVIEW;

  useEffect(() => {
    const results: AnalyzedStock[] = DEMO_STOCKS.map(stock => {
      const history = generateHistoricalPrices(stock);
      const fcs = computeFCS(stock, history, DEFAULT_WEIGHTS);
      return {
        stock,
        fcs: fcs.score,
        signal: fcs.signal,
        fvl: fcs.layerScores.fvl,
        tml: fcs.layerScores.tml,
        ssil: fcs.layerScores.ssil,
        gtbil: fcs.layerScores.gtbil,
        mrlll: fcs.layerScores.mrlll,
      };
    });
    results.sort((a, b) => b.fcs - a.fcs);
    setAnalyzed(results);
    setLoading(false);
  }, []);

  const topPicks = analyzed.slice(0, 5);

  // Sector performance chart data
  const sectorData = DEMO_SECTOR_PERFORMANCE.map(s => ({
    name: s.sector.replace(' & ', '/').substring(0, 12),
    change: s.changePercent,
  }));

  // Radar data for top pick
  const radarData = topPicks.length > 0 ? [
    { layer: 'FVL', score: topPicks[0].fvl },
    { layer: 'TML', score: topPicks[0].tml },
    { layer: 'SSIL', score: topPicks[0].ssil },
    { layer: 'GTBIL', score: topPicks[0].gtbil },
    { layer: 'MRLLL', score: topPicks[0].mrlll },
  ] : [];

  // Generate NEPSE index chart data
  const indexData = Array.from({ length: 30 }, (_, i) => ({
    day: i + 1,
    value: 2700 + Math.sin(i / 5) * 50 + i * 5 + Math.random() * 20,
  }));

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Market Intelligence Dashboard</h2>
          <div className="subtitle">NEPSE-ALPHA ULTIMATE · Five-Layer Prediction Engine</div>
          <div className="data-badge demo">
            <span className="pulse"></span>
            DEMO DATA · {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </div>
        </div>

        {/* Market Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">NEPSE Index</div>
            <div className="stat-value">{market.nepseIndex.toLocaleString()}</div>
            <div className={`stat-change ${market.nepseChangePercent >= 0 ? 'positive' : 'negative'}`}>
              {market.nepseChangePercent >= 0 ? '▲' : '▼'} {Math.abs(market.nepseChange).toFixed(2)} ({Math.abs(market.nepseChangePercent).toFixed(2)}%)
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Turnover</div>
            <div className="stat-value">Rs.{(market.totalTurnover / 1e9).toFixed(2)}B</div>
            <div className="stat-change positive">Daily Volume: {(market.totalVolume / 1e6).toFixed(1)}M</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Market Breadth</div>
            <div className="stat-value" style={{ color: market.advancers > market.decliners ? 'var(--bullish)' : 'var(--bearish)' }}>
              {market.advancers}/{market.decliners}
            </div>
            <div className="stat-change positive">Adv/Dec · {market.unchanged} unchanged</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Interbank Rate</div>
            <div className="stat-value">{market.interbankRate}%</div>
            <div className={`stat-change ${market.interbankRate < 5 ? 'positive' : 'negative'}`}>
              {market.interbankRate < 5 ? 'Comfortable Liquidity' : 'Tightening'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">91-Day T-Bill</div>
            <div className="stat-value">{market.tBillYield}%</div>
            <div className="stat-change">Risk-free benchmark</div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          {/* NEPSE Index Chart */}
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">NEPSE Index · 30 Day</div>
              <span className="signal-badge strong-buy" style={{ fontSize: '0.65rem' }}>
                {market.regime}
              </span>
            </div>
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={indexData}>
                  <defs>
                    <linearGradient id="indexGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <YAxis domain={['auto', 'auto']} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8ecf4' }} />
                  <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fill="url(#indexGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sector Performance */}
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Sector Performance</div>
            </div>
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sectorData} layout="vertical">
                  <XAxis type="number" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#8b95b0', fontSize: 10 }} width={85} />
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8ecf4' }} />
                  <Bar dataKey="change" radius={[0, 4, 4, 0]} fill="#6366f1">
                    {sectorData.map((entry, index) => (
                      <rect key={`cell-${index}`} fill={entry.change >= 0 ? '#00e676' : '#ff5252'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Top 5 Daily Picks */}
        <div className="glass-card" style={{ marginBottom: 24 }}>
          <div className="glass-card-header">
            <div className="glass-card-title">🎯 Top 5 Daily Signals</div>
            <a href="/predictions" style={{ fontSize: '0.78rem', fontWeight: 600 }}>View All →</a>
          </div>
          {loading ? (
            <div style={{ display: 'flex', gap: 16 }}>
              {[1,2,3,4,5].map(i => <div key={i} className="loading-skeleton" style={{ height: 140, flex: 1, borderRadius: 12 }} />)}
            </div>
          ) : (
            <div className="predictions-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
              {topPicks.map((a, i) => (
                <div key={a.stock.symbol} className={`prediction-card ${getSignalClass(a.signal)}`}>
                  <div className="rank-badge">{i + 1}</div>
                  <div className="pred-header">
                    <div>
                      <div className="pred-symbol">{a.stock.symbol}</div>
                      <div className="pred-name" style={{ maxWidth: 120 }}>{a.stock.name}</div>
                    </div>
                  </div>
                  <span className={`signal-badge ${getSignalClass(a.signal)}`}>{a.signal}</span>
                  <div className="pred-metrics" style={{ marginTop: 12, gridTemplateColumns: '1fr 1fr' }}>
                    <div className="pred-metric">
                      <div className="pred-metric-label">FCS</div>
                      <div className="pred-metric-value">{a.fcs}</div>
                    </div>
                    <div className="pred-metric">
                      <div className="pred-metric-label">CMP</div>
                      <div className="pred-metric-value">₹{a.stock.cmp}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="dashboard-grid grid-2">
          {/* Radar chart for top pick */}
          {radarData.length > 0 && (
            <div className="glass-card">
              <div className="glass-card-header">
                <div className="glass-card-title">Top Pick Layer Analysis — {topPicks[0]?.stock.symbol}</div>
              </div>
              <div style={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="rgba(255,255,255,0.06)" />
                    <PolarAngleAxis dataKey="layer" tick={{ fill: '#8b95b0', fontSize: 11, fontWeight: 600 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#5a6580', fontSize: 9 }} />
                    <Radar name="Score" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} strokeWidth={2} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Layer weights display */}
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Active Layer Weights · Bull Trend</div>
            </div>
            <div className="layer-breakdown" style={{ marginTop: 8 }}>
              {[
                { key: 'fvl', label: 'FVL', weight: 25, desc: 'Fundamental Value Layer' },
                { key: 'tml', label: 'TML', weight: 25, desc: 'Technical Momentum' },
                { key: 'ssil', label: 'SSIL', weight: 15, desc: 'Social Sentiment' },
                { key: 'gtbil', label: 'GTBIL', weight: 25, desc: 'Broker Intelligence' },
                { key: 'mrlll', label: 'MRLLL', weight: 10, desc: 'Macro Lead-Lag' },
              ].map(l => (
                <div className="layer-row" key={l.key}>
                  <div className="layer-label">{l.label}</div>
                  <div className="layer-bar-track">
                    <div className={`layer-bar-fill ${l.key}`} style={{ width: `${l.weight * 2}%` }}></div>
                  </div>
                  <div className="layer-score-number">{l.weight}%</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20, padding: '12px 16px', background: 'rgba(99,102,241,0.06)', borderRadius: 8, fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <strong style={{ color: 'var(--accent-primary)' }}>Regime:</strong> Bull Trend · Confidence 72%<br/>
              <strong style={{ color: 'var(--accent-primary)' }}>Strategy:</strong> Ride momentum. Trust technical signals. Let winners run.<br/>
              <strong style={{ color: 'var(--accent-primary)' }}>Best Signals:</strong> D2, D4, W1, W3<br/>
              <strong style={{ color: 'var(--accent-primary)' }}>Position Multiplier:</strong> 1.0x
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
