'use client';

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { generateHistoricalPrices } from '@/lib/demo-data';
import { fetchLiveStocks } from '@/lib/api-client';
import { analyzeStock, computeTechnicalIndicators, FullAnalysis } from '@/lib/analysis-engine';
import { LayerWeights, Stock } from '@/lib/types';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  BarChart, Bar,
} from 'recharts';

const DEFAULT_WEIGHTS: LayerWeights = { fvl: 0.25, tml: 0.25, ssil: 0.15, gtbil: 0.25, mrlll: 0.10 };

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

function AnalysisContent() {
  const searchParams = useSearchParams();
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [dataSource, setDataSource] = useState<'LIVE' | 'DEMO'>('DEMO');
  const symbolParam = searchParams.get('symbol');
  const [symbol, setSymbol] = useState<string>('');
  const [analysis, setAnalysis] = useState<FullAnalysis | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const stocksData = await fetchLiveStocks();
      setStocks(stocksData.stocks);
      setDataSource(stocksData.source);
      
      // Use the symbol from URL or default to first stock
      const targetSymbol = symbolParam || stocksData.stocks[0]?.symbol || '';
      setSymbol(targetSymbol);
      
      const stock = stocksData.stocks.find(s => s.symbol === targetSymbol) || stocksData.stocks[0];
      if (stock) {
        const hist = generateHistoricalPrices(stock);
        const result = analyzeStock(stock, hist, DEFAULT_WEIGHTS);
        setAnalysis(result);
        const indicators = computeTechnicalIndicators(hist, stock);
        // Build chart data
        const chartData = hist.map((h, i) => ({
          date: h.date.substring(5),
          close: h.close,
          volume: h.volume,
          ema9: i >= 8 ? hist.slice(0, i + 1).reduce((acc, v, j) => {
            const k = 2 / 10;
            return j === 0 ? v.close : v.close * k + acc * (1 - k);
          }, 0) : null,
        }));
        setHistory(chartData);
      }
      setLoading(false);
    }
    
    loadData();
  }, [symbolParam]);

  if (loading || !analysis) {
    return <div style={{ padding: 40 }}><div className="loading-skeleton" style={{ height: 400, borderRadius: 16 }} /></div>;
  }

  const a = analysis;
  const radarData = [
    { layer: 'FVL', score: a.fcs.layerScores.fvl },
    { layer: 'TML', score: a.fcs.layerScores.tml },
    { layer: 'SSIL', score: a.fcs.layerScores.ssil },
    { layer: 'GTBIL', score: a.fcs.layerScores.gtbil },
    { layer: 'MRLLL', score: a.fcs.layerScores.mrlll },
  ];

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h2>{a.stock.symbol}</h2>
          <span className={`signal-badge ${getSignalClass(a.fcs.signal)}`} style={{ fontSize: '0.8rem' }}>{a.fcs.signal}</span>
        </div>
        <div className="subtitle">{a.stock.name} · {a.stock.sector}</div>
        <div className={`data-badge ${dataSource === 'LIVE' ? 'live' : 'demo'}`}><span className="pulse"></span>{dataSource === 'LIVE' ? 'LIVE' : 'DEMO'} · Full Five-Layer Report</div>
      </div>

      {/* Price Stats Bar */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        <div className="stat-card">
          <div className="stat-label">CMP</div>
          <div className="stat-value" style={{ fontSize: '1.3rem' }}>Rs.{a.stock.cmp.toLocaleString()}</div>
          <div className={`stat-change ${a.stock.changePercent >= 0 ? 'positive' : 'negative'}`}>
            {a.stock.changePercent >= 0 ? '+' : ''}{a.stock.changePercent.toFixed(2)}%
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">BSTS Fair Value</div>
          <div className="stat-value" style={{ fontSize: '1.3rem' }}>Rs.{a.bstsFairValue}</div>
          <div className={`stat-change ${a.overvaluationPercent < 0 ? 'positive' : 'negative'}`}>
            {a.overvaluationPercent > 0 ? '+' : ''}{a.overvaluationPercent}% vs fair
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">PT1 Target</div>
          <div className="stat-value target" style={{ fontSize: '1.3rem', color: 'var(--bullish)' }}>Rs.{a.priceTargets.pt1}</div>
          <div className="stat-change positive">+{((a.priceTargets.pt1 / a.stock.cmp - 1) * 100).toFixed(1)}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">PT2 Extended</div>
          <div className="stat-value" style={{ fontSize: '1.3rem', color: 'var(--accent-primary)' }}>Rs.{a.priceTargets.pt2}</div>
          <div className="stat-change positive">+{((a.priceTargets.pt2 / a.stock.cmp - 1) * 100).toFixed(1)}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Stop Loss</div>
          <div className="stat-value" style={{ fontSize: '1.3rem', color: 'var(--bearish)' }}>Rs.{a.priceTargets.stopLoss}</div>
          <div className="stat-change negative">{((a.priceTargets.stopLoss / a.stock.cmp - 1) * 100).toFixed(1)}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">FCS Score</div>
          <div className="stat-value" style={{ fontSize: '1.8rem', color: a.fcs.score >= 70 ? 'var(--bullish)' : a.fcs.score >= 50 ? 'var(--hold)' : 'var(--bearish)' }}>
            {Math.round(a.fcs.score)}
          </div>
        </div>
      </div>

      <div className="dashboard-grid grid-2" style={{ margin: '24px 0' }}>
        {/* Price Chart */}
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Price Chart · 60 Day</div>
          </div>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 9 }} interval={6} />
                <YAxis domain={['auto', 'auto']} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8ecf4' }} />
                <ReferenceLine y={a.priceTargets.pt1} stroke="#00e676" strokeDasharray="6 4" label={{ value: `PT1: ${a.priceTargets.pt1}`, fill: '#00e676', fontSize: 10 }} />
                <ReferenceLine y={a.priceTargets.stopLoss} stroke="#ff5252" strokeDasharray="6 4" label={{ value: `SL: ${a.priceTargets.stopLoss}`, fill: '#ff5252', fontSize: 10 }} />
                <Line type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Radar + FCS */}
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Five-Layer Radar</div>
          </div>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis dataKey="layer" tick={{ fill: '#8b95b0', fontSize: 12, fontWeight: 700 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#5a6580', fontSize: 9 }} />
                <Radar name="Score" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} strokeWidth={2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Layer Breakdown */}
      <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Layer Score Breakdown</div>
          </div>
          <div className="layer-breakdown">
            {[
              { key: 'fvl', label: 'FVL', score: a.fcs.layerScores.fvl, weight: (a.fcs.weights.fvl * 100).toFixed(0) },
              { key: 'tml', label: 'TML', score: a.fcs.layerScores.tml, weight: (a.fcs.weights.tml * 100).toFixed(0) },
              { key: 'ssil', label: 'SSIL', score: a.fcs.layerScores.ssil, weight: (a.fcs.weights.ssil * 100).toFixed(0) },
              { key: 'gtbil', label: 'GTBIL', score: a.fcs.layerScores.gtbil, weight: (a.fcs.weights.gtbil * 100).toFixed(0) },
              { key: 'mrlll', label: 'MRLLL', score: a.fcs.layerScores.mrlll, weight: (a.fcs.weights.mrlll * 100).toFixed(0) },
            ].map(l => (
              <div className="layer-row" key={l.key}>
                <div className="layer-label">{l.label}</div>
                <div className="layer-bar-track">
                  <div className={`layer-bar-fill ${l.key}`} style={{ width: `${l.score}%` }} />
                </div>
                <div className="layer-score-number">{Math.round(l.score)}</div>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', width: 30 }}>×{l.weight}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Warning Flags */}
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">⚠ Warning Flags</div>
          </div>
          <div className="warning-panel">
            <div className="warning-item">
              <div className="warning-label">SIS Score</div>
              <div className={`warning-value ${a.warningFlags.sisScore < 50 ? 'safe' : a.warningFlags.sisScore < 75 ? 'caution' : 'danger'}`}>
                {Math.round(a.warningFlags.sisScore)} — {a.warningFlags.sisLevel}
              </div>
            </div>
            <div className="warning-item">
              <div className="warning-label">BMR</div>
              <div className={`warning-value ${a.warningFlags.bmr > 35 ? 'safe' : a.warningFlags.bmr > 20 ? 'caution' : 'danger'}`}>
                {Math.round(a.warningFlags.bmr)}% — {a.warningFlags.bmrLevel}
              </div>
            </div>
            <div className="warning-item">
              <div className="warning-label">TTH Status</div>
              <div className="warning-value safe">{a.warningFlags.tthStatus}</div>
            </div>
            <div className="warning-item">
              <div className="warning-label">Political Risk</div>
              <div className="warning-value safe">{a.warningFlags.politicalRisk}</div>
            </div>
            <div className="warning-item">
              <div className="warning-label">BSTS Confidence</div>
              <div className="warning-value safe">{a.warningFlags.bstsConfidence}</div>
            </div>
            <div className="warning-item">
              <div className="warning-label">Circular Trading</div>
              <div className="warning-value safe">{a.warningFlags.circularTrading ? 'DETECTED' : 'None'}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Layer Details */}
      <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
        {[
          { title: 'Fundamental Value (FVL)', details: a.fvlDetails, color: '#6366f1' },
          { title: 'Technical Momentum (TML)', details: a.tmlDetails, color: '#06b6d4' },
          { title: 'Social Sentiment (SSIL)', details: a.ssilDetails, color: '#f59e0b' },
          { title: 'Broker Intelligence (GTBIL)', details: a.gtbilDetails, color: '#10b981' },
        ].map(section => (
          <div className="glass-card" key={section.title}>
            <div className="glass-card-header">
              <div className="glass-card-title" style={{ color: section.color }}>{section.title}</div>
            </div>
            <ul className="detail-list">
              {section.details.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          </div>
        ))}
      </div>

      {/* Retail vs Institutional Verdict */}
      <div className="glass-card" style={{ marginBottom: 24 }}>
        <div className="glass-card-header">
          <div className="glass-card-title">Retail vs. Institutional Divergence Verdict</div>
        </div>
        <div className="verdict-box">{a.retailInstitutionalVerdict}</div>
      </div>

      {/* Override Conditions */}
      <div className="glass-card">
        <div className="glass-card-header">
          <div className="glass-card-title">Override Conditions</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {a.fcs.overrides.map(o => (
            <div key={o.id} className="warning-item" style={{ borderColor: o.triggered ? 'var(--bearish)' : 'var(--border-subtle)' }}>
              <div className="warning-label">{o.name}</div>
              <div className={`warning-value ${o.triggered ? 'danger' : 'safe'}`}>{o.triggered ? 'TRIGGERED' : 'Clear'}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default function AnalysisPage() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Suspense fallback={<div style={{ padding: 40 }}><div className="loading-skeleton" style={{ height: 400, borderRadius: 16 }} /></div>}>
          <AnalysisContent />
        </Suspense>
      </main>
    </div>
  );
}
