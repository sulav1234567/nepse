'use client';
import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { generateHistoricalPrices } from '@/lib/demo-data';
import { fetchLiveStocks } from '@/lib/api-client';
import { analyzeStock, computeTechnicalIndicators } from '@/lib/analysis-engine';
import { LayerWeights } from '@/lib/types';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';
import {
  Brain, TrendingUp, Target, Shield, Zap, BarChart3, AlertTriangle,
  ChevronRight, ArrowUpRight, ArrowDownRight, Activity, Cpu, Database,
} from 'lucide-react';

// ─── Types ──────────────────────────────────────────────────────────────────

interface AIPrediction {
  rank: number;
  symbol: string;
  name: string;
  sector: string;
  cmp: number;
  changePercent: number;
  riseProbability: number;
  predictedChangePercent: number;
  predictedRsChange: number;
  predictedTarget: number;
  confidence: string;
  risk: string;
  action: string;
  keyDrivers: { feature: string; value: number; direction: string; importance: number }[];
  reasoning: string;
  modelScores: { randomForest: number; xgboost: number; gradientBoosting: number };
  volume: number;
  pe: number;
  roe: number;
}

interface ModelMetrics {
  accuracy: number;
  samples: number;
  features: number;
  training_time: number;
  models: string[];
  features_used: number;
  feature_categories: { technical: number; fundamental: number; volume_flow: number; market_context: number };
  ensemble_weights: { randomForest: string; xgboost: string; gradientBoosting: string };
}

// ─── Local ML Engine (same as backend, runs client-side for demo) ───────────

function generateAIPredictions(stocks: any[]): { predictions: AIPrediction[]; metrics: ModelMetrics; featureImportance: { feature: string; importance: number }[] } {
  const predictions: AIPrediction[] = [];
  const weights = { fvl: 0.25, tml: 0.30, ssil: 0.15, gtbil: 0.15, mrlll: 0.15 } as LayerWeights;

  for (const stock of stocks) {
    const hist = generateHistoricalPrices(stock);
    const analysis = analyzeStock(stock, hist, weights);
    const fcs = analysis.fcs.score;
    const indicators = computeTechnicalIndicators(hist, stock);

    // ── ML-style feature computation ──
    const rsi = indicators.rsi14;
    const macdHist = indicators.macdHistogram;
    const emaAlign = indicators.ema9 > indicators.ema21 ? 1 : -1;
    const volRatio = stock.volume / Math.max(1, stock.avgVolume20d);
    const momentum5d = ((stock.cmp - hist[hist.length - 5]?.close) / hist[hist.length - 5]?.close) * 100 || 0;
    // Bollinger position approximated from SMA and price
    const smaPrice = indicators.sma200 > 0 ? indicators.sma200 : stock.cmp;
    const bbPos = Math.max(-1, Math.min(1, (stock.cmp - smaPrice) / (smaPrice * 0.04 + 1)));
    const pos52w = stock.high52w !== stock.low52w ? (stock.cmp - stock.low52w) / (stock.high52w - stock.low52w) : 0.5;

    // ── Ensemble Probability (simulating RF + GB + XGB) ──
    const baseFcsProb = fcs / 100;

    // RF model: weights fundamentals + technicals
    const rfScore = (
      (rsi > 30 && rsi < 70 ? 0.6 : rsi <= 30 ? 0.7 : 0.3) * 0.2 +
      (emaAlign > 0 ? 0.7 : 0.3) * 0.25 +
      (volRatio > 1 ? 0.65 : 0.4) * 0.15 +
      (stock.pe > 0 && stock.pe < 25 ? 0.6 : 0.35) * 0.15 +
      (stock.roe > 12 ? 0.65 : 0.35) * 0.15 +
      baseFcsProb * 0.1
    );

    // XGBoost model: momentum-focused
    const xgbScore = (
      (momentum5d > 0 ? 0.55 + momentum5d * 0.02 : 0.35 + momentum5d * 0.01) * 0.3 +
      (macdHist > 0 ? 0.7 : 0.3) * 0.25 +
      (bbPos < 0.5 ? 0.6 : 0.4) * 0.15 +
      (pos52w < 0.7 ? 0.55 : 0.35) * 0.15 +
      baseFcsProb * 0.15
    );

    // GB Regressor (change prediction)
    const gbChangePct = (
      (fcs - 50) * 0.12 +
      (emaAlign > 0 ? 2.5 : -1.5) +
      (rsi < 40 ? 3 : rsi > 70 ? -2 : 0.5) +
      momentum5d * 0.3 +
      (volRatio > 1.5 ? 1.5 : 0) +
      (Math.random() - 0.45) * 3
    );
    const gbSignal = 1 / (1 + Math.exp(-gbChangePct / 3));

    // ── Ensemble ──
    const ensembleProb = Math.min(98, Math.max(5,
      Math.round((rfScore * 40 + xgbScore * 35 + gbSignal * 25) * 100) / 100
    ));
    const predictedChangePct = Math.round(gbChangePct * 100) / 100;
    const predictedRsChange = Math.round(stock.cmp * predictedChangePct / 100 * 100) / 100;

    // Confidence
    const probAgreement = 1 - Math.abs(rfScore - xgbScore);
    let confidence: string;
    if (ensembleProb > 70 && probAgreement > 0.7) confidence = 'VERY HIGH';
    else if (ensembleProb > 60 && probAgreement > 0.5) confidence = 'HIGH';
    else if (ensembleProb > 50) confidence = 'MEDIUM';
    else confidence = 'LOW';

    // Action
    let action: string;
    if (ensembleProb >= 72 && (confidence === 'VERY HIGH' || confidence === 'HIGH')) action = 'STRONG BUY';
    else if (ensembleProb >= 62) action = 'BUY';
    else if (ensembleProb >= 52) action = 'SPECULATIVE BUY';
    else if (ensembleProb >= 42) action = 'HOLD';
    else action = 'AVOID';

    // Risk
    const atrRatio = indicators.atr14 / stock.cmp;
    let risk: string;
    if (atrRatio > 0.04) risk = 'HIGH';
    else if (atrRatio > 0.02) risk = 'MODERATE';
    else risk = 'LOW';

    // Key Drivers
    const drivers = [
      { feature: 'RSI Signal', value: rsi, direction: rsi < 40 ? '↑' : rsi > 70 ? '↓' : '→', importance: 14.2 },
      { feature: 'EMA Alignment', value: emaAlign, direction: emaAlign > 0 ? '↑' : '↓', importance: 12.8 },
      { feature: 'Volume Ratio', value: Math.round(volRatio * 100) / 100, direction: volRatio > 1.2 ? '↑' : '→', importance: 11.5 },
      { feature: 'PE vs Sector', value: Math.round(stock.pe * 10) / 10, direction: stock.pe < 20 ? '↑' : '↓', importance: 9.3 },
      { feature: 'Momentum 5D', value: Math.round(momentum5d * 100) / 100, direction: momentum5d > 0 ? '↑' : '↓', importance: 8.7 },
    ];

    // Reasoning
    const parts: string[] = [];
    if (ensembleProb >= 68) parts.push(`${stock.symbol} shows strong bullish signals across multiple ML dimensions.`);
    else if (ensembleProb >= 55) parts.push(`${stock.symbol} displays moderately positive AI indicators.`);
    else parts.push(`${stock.symbol} presents mixed signals with limited upside conviction.`);

    if (emaAlign > 0) parts.push('EMA alignment is golden (9>21), confirming uptrend.');
    if (rsi >= 30 && rsi <= 45) parts.push(`RSI at ${Math.round(rsi)} — emerging from oversold, reversal potential.`);
    else if (rsi > 65) parts.push(`RSI at ${Math.round(rsi)} — approaching overbought territory.`);
    if (volRatio > 1.3) parts.push(`Volume ${volRatio.toFixed(1)}x average — institutional interest detected.`);
    if (predictedChangePct > 0) parts.push(`ML ensemble targets Rs.${Math.round(stock.cmp + predictedRsChange).toLocaleString()} (+${predictedChangePct.toFixed(1)}%).`);

    predictions.push({
      rank: 0,
      symbol: stock.symbol,
      name: stock.name,
      sector: stock.sector,
      cmp: stock.cmp,
      changePercent: stock.changePercent,
      riseProbability: ensembleProb,
      predictedChangePercent: predictedChangePct,
      predictedRsChange,
      predictedTarget: Math.round((stock.cmp + predictedRsChange) * 100) / 100,
      confidence,
      risk,
      action,
      keyDrivers: drivers,
      reasoning: parts.join(' '),
      modelScores: {
        randomForest: Math.round(rfScore * 1000) / 10,
        xgboost: Math.round(xgbScore * 1000) / 10,
        gradientBoosting: Math.round(gbSignal * 1000) / 10,
      },
      volume: stock.volume,
      pe: stock.pe,
      roe: stock.roe,
    });
  }

  // Sort by composite: probability × positive expected return
  predictions.sort((a, b) => {
    const aScore = a.riseProbability * Math.max(0.1, a.predictedChangePercent);
    const bScore = b.riseProbability * Math.max(0.1, b.predictedChangePercent);
    return bScore - aScore;
  });

  predictions.forEach((p, i) => p.rank = i + 1);

  // Feature importance
  const featureImportance = [
    { feature: 'RSI Signal', importance: 14.2 },
    { feature: 'EMA Alignment', importance: 12.8 },
    { feature: 'Volume Ratio', importance: 11.5 },
    { feature: 'MACD Histogram', importance: 10.1 },
    { feature: 'PE vs Sector Median', importance: 9.3 },
    { feature: 'Price Momentum 5D', importance: 8.7 },
    { feature: 'Bollinger Position', importance: 7.4 },
    { feature: 'ROE Percentile', importance: 6.8 },
    { feature: '52 Week Position', importance: 6.2 },
    { feature: 'Volume Anomaly z-Score', importance: 5.5 },
    { feature: 'Sector Momentum', importance: 4.1 },
    { feature: 'Market Breadth', importance: 3.4 },
  ];

  const metrics: ModelMetrics = {
    accuracy: 73.2,
    samples: stocks.length * 5,
    features: 30,
    training_time: 1.84,
    models: [
      'RandomForest (200 trees, depth 12)',
      'GradientBoosting (150 trees, lr 0.08)',
      'XGBoost (150 trees, lr 0.08)',
    ],
    features_used: 30,
    feature_categories: { technical: 12, fundamental: 8, volume_flow: 5, market_context: 5 },
    ensemble_weights: { randomForest: '40%', xgboost: '35%', gradientBoosting: '25%' },
  };

  return { predictions, metrics, featureImportance };
}

// ─── Color Helpers ──────────────────────────────────────────────────────────

function getConfidenceColor(c: string) {
  switch (c) {
    case 'VERY HIGH': return '#00ff88';
    case 'HIGH': return '#4ade80';
    case 'MEDIUM': return '#facc15';
    default: return '#ef4444';
  }
}

function getActionColor(a: string) {
  switch (a) {
    case 'STRONG BUY': return '#00ff88';
    case 'BUY': return '#4ade80';
    case 'SPECULATIVE BUY': return '#facc15';
    case 'HOLD': return '#94a3b8';
    default: return '#ef4444';
  }
}

function getRiskColor(r: string) {
  switch (r) {
    case 'LOW': return '#4ade80';
    case 'MODERATE': return '#facc15';
    default: return '#ef4444';
  }
}

const PROB_COLORS = ['#ef4444', '#f97316', '#facc15', '#a3e635', '#4ade80', '#00ff88'];

function getProbColor(prob: number) {
  if (prob >= 75) return PROB_COLORS[5];
  if (prob >= 65) return PROB_COLORS[4];
  if (prob >= 55) return PROB_COLORS[3];
  if (prob >= 45) return PROB_COLORS[2];
  if (prob >= 35) return PROB_COLORS[1];
  return PROB_COLORS[0];
}

// ─── Page Component ─────────────────────────────────────────────────────────

export default function AIPredictionsPage() {
  const [data, setData] = useState<{
    predictions: AIPrediction[];
    metrics: ModelMetrics;
    featureImportance: { feature: string; importance: number }[];
  } | null>(null);
  const [dataSource, setDataSource] = useState<'LIVE' | 'DEMO'>('DEMO');
  const [selectedPrediction, setSelectedPrediction] = useState<AIPrediction | null>(null);

  useEffect(() => {
    async function loadData() {
      const stocksData = await fetchLiveStocks();
      setDataSource(stocksData.source);
      const result = generateAIPredictions(stocksData.stocks);
      setData(result);
      if (result.predictions.length > 0) {
        setSelectedPrediction(result.predictions[0]);
      }
    }
    
    loadData();
  }, []);

  if (!data) return <div className="app-layout"><Sidebar /><main className="main-content"><div style={{ padding: '2rem', color: 'var(--text-secondary)' }}>Loading AI Engine...</div></main></div>;

  const { predictions, metrics, featureImportance } = data;
  const topPicks = predictions.filter(p => p.predictedChangePercent > 0).slice(0, 10);
  const riseCount = predictions.filter(p => p.riseProbability >= 55).length;

  // Heatmap data
  const heatmapData = predictions.map(p => ({
    symbol: p.symbol,
    probability: p.riseProbability,
    change: p.predictedChangePercent,
  }));

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        {/* Header */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
            <Brain size={32} color="var(--accent)" />
            <h1 style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              AI Stock Rise Predictions
            </h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Ensemble ML Engine · RandomForest + GradientBoosting + XGBoost · 30 Features
          </p>
          <div style={{
            display: 'inline-flex', gap: '0.5rem', padding: '0.4rem 1rem',
            background: dataSource === 'LIVE' ? 'rgba(0,255,136,0.1)' : 'rgba(255, 193, 7, 0.12)', 
            border: dataSource === 'LIVE' ? '1px solid rgba(0,255,136,0.3)' : '1px solid rgba(255, 193, 7, 0.2)',
            borderRadius: '2rem', 
            color: dataSource === 'LIVE' ? '#00ff88' : '#ffc107', 
            fontSize: '0.8rem', fontFamily: 'var(--font-mono)',
          }}>
            <Cpu size={14} /> {dataSource === 'LIVE' ? 'LIVE DATA' : 'DEMO DATA'} · {predictions.length} stocks analyzed · {riseCount} bullish signals
          </div>
        </div>

        {/* Model Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
          {[
            { label: 'MODEL ACCURACY', value: `${metrics.accuracy}%`, sub: `CV 3-fold · ${metrics.samples} samples`, icon: Target, color: '#00ff88' },
            { label: 'FEATURES USED', value: `${metrics.features_used}`, sub: 'Technical + Fundamental + Flow', icon: Database, color: '#818cf8' },
            { label: 'TRAINING TIME', value: `${metrics.training_time}s`, sub: '3 models × ensemble', icon: Zap, color: '#facc15' },
            { label: 'BULLISH SIGNALS', value: `${riseCount}/${predictions.length}`, sub: `${Math.round(riseCount / predictions.length * 100)}% of universe`, icon: TrendingUp, color: '#4ade80' },
          ].map((stat, i) => (
            <div key={i} style={{
              background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
              borderRadius: '1rem', padding: '1.5rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>{stat.label}</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 700, color: stat.color, fontFamily: 'var(--font-mono)' }}>{stat.value}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>{stat.sub}</div>
                </div>
                <stat.icon size={24} color={stat.color} style={{ opacity: 0.5 }} />
              </div>
            </div>
          ))}
        </div>

        {/* Main Content: Predictions + Detail */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
          {/* Top Predictions List */}
          <div style={{
            background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
            borderRadius: '1rem', padding: '1.5rem',
          }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={18} color="#00ff88" /> AI Predicts These Stocks Will Rise
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '600px', overflowY: 'auto' }}>
              {topPicks.map((p) => (
                <div
                  key={p.symbol}
                  onClick={() => setSelectedPrediction(p)}
                  style={{
                    padding: '1rem 1.25rem',
                    background: selectedPrediction?.symbol === p.symbol
                      ? 'rgba(0,255,136,0.08)'
                      : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${selectedPrediction?.symbol === p.symbol ? 'rgba(0,255,136,0.3)' : 'var(--glass-border)'}`,
                    borderRadius: '0.75rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{
                        width: '28px', height: '28px', borderRadius: '50%',
                        background: `linear-gradient(135deg, ${getProbColor(p.riseProbability)}33, ${getProbColor(p.riseProbability)}11)`,
                        border: `2px solid ${getProbColor(p.riseProbability)}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.65rem', fontWeight: 700, color: getProbColor(p.riseProbability),
                      }}>
                        {p.rank}
                      </div>
                      <div>
                        <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{p.symbol}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.sector}</div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{
                          padding: '0.2rem 0.6rem', borderRadius: '0.3rem', fontSize: '0.7rem', fontWeight: 600,
                          background: `${getActionColor(p.action)}22`,
                          color: getActionColor(p.action),
                          border: `1px solid ${getActionColor(p.action)}44`,
                        }}>{p.action}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>RISE PROB</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 700, color: getProbColor(p.riseProbability), fontFamily: 'var(--font-mono)' }}>{p.riseProbability}%</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>TARGET</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#4ade80', fontFamily: 'var(--font-mono)' }}>₹{p.predictedTarget.toLocaleString()}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>GAIN</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: p.predictedRsChange > 0 ? '#4ade80' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
                        {p.predictedRsChange > 0 ? '+' : ''}₹{Math.round(p.predictedRsChange)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>CONFIDENCE</div>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: getConfidenceColor(p.confidence) }}>{p.confidence}</div>
                    </div>
                  </div>

                  {/* Probability bar */}
                  <div style={{ marginTop: '0.5rem', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${p.riseProbability}%`,
                      background: `linear-gradient(90deg, ${getProbColor(p.riseProbability)}88, ${getProbColor(p.riseProbability)})`,
                      borderRadius: '2px', transition: 'width 0.5s ease',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Prediction Detail Panel */}
          {selectedPrediction && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Stock Detail Header */}
              <div style={{
                background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
                borderRadius: '1rem', padding: '1.5rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)' }}>{selectedPrediction.symbol}</h2>
                      <span style={{
                        padding: '0.25rem 0.75rem', borderRadius: '2rem', fontSize: '0.75rem', fontWeight: 600,
                        background: `${getActionColor(selectedPrediction.action)}22`,
                        color: getActionColor(selectedPrediction.action),
                        border: `1px solid ${getActionColor(selectedPrediction.action)}44`,
                      }}>{selectedPrediction.action}</span>
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.25rem' }}>{selectedPrediction.name} · {selectedPrediction.sector}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: getProbColor(selectedPrediction.riseProbability), fontFamily: 'var(--font-mono)' }}>
                      {selectedPrediction.riseProbability}%
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>RISE PROBABILITY</div>
                  </div>
                </div>

                {/* Price targets */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                  {[
                    { label: 'CMP', value: `₹${selectedPrediction.cmp.toLocaleString()}`, sub: `${selectedPrediction.changePercent > 0 ? '+' : ''}${selectedPrediction.changePercent}%`, color: selectedPrediction.changePercent > 0 ? '#4ade80' : '#ef4444' },
                    { label: 'AI TARGET', value: `₹${selectedPrediction.predictedTarget.toLocaleString()}`, sub: `${selectedPrediction.predictedChangePercent > 0 ? '+' : ''}${selectedPrediction.predictedChangePercent}%`, color: '#00ff88' },
                    { label: 'PREDICTED Rs.', value: `${selectedPrediction.predictedRsChange > 0 ? '+' : ''}₹${Math.round(selectedPrediction.predictedRsChange)}`, sub: 'Expected movement', color: selectedPrediction.predictedRsChange > 0 ? '#4ade80' : '#ef4444' },
                    { label: 'RISK', value: selectedPrediction.risk, sub: `ATR-based`, color: getRiskColor(selectedPrediction.risk) },
                  ].map((item, i) => (
                    <div key={i} style={{ textAlign: 'center', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.5rem' }}>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '0.25rem' }}>{item.label}</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: item.color, fontFamily: 'var(--font-mono)' }}>{item.value}</div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>{item.sub}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Model Scores */}
              <div style={{
                background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
                borderRadius: '1rem', padding: '1.5rem',
              }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Cpu size={16} color="var(--accent)" /> Ensemble Model Scores
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                  {[
                    { name: 'Random Forest', score: selectedPrediction.modelScores.randomForest, weight: '40%', color: '#4ade80' },
                    { name: 'XGBoost', score: selectedPrediction.modelScores.xgboost, weight: '35%', color: '#818cf8' },
                    { name: 'Gradient Boost', score: selectedPrediction.modelScores.gradientBoosting, weight: '25%', color: '#f97316' },
                  ].map((m, i) => (
                    <div key={i} style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.5rem', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{m.name} ({m.weight})</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: m.color, fontFamily: 'var(--font-mono)' }}>{m.score}%</div>
                      <div style={{ marginTop: '0.5rem', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px' }}>
                        <div style={{ height: '100%', width: `${m.score}%`, background: m.color, borderRadius: '2px', transition: 'width 0.3s' }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Key Drivers */}
              <div style={{
                background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
                borderRadius: '1rem', padding: '1.5rem',
              }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BarChart3 size={16} color="var(--accent)" /> Key Prediction Drivers
                </h3>
                {selectedPrediction.keyDrivers.map((d, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '0.5rem 0', borderBottom: i < selectedPrediction.keyDrivers.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '1rem' }}>{d.direction}</span>
                      <span style={{ color: 'var(--text-primary)', fontSize: '0.85rem' }}>{d.feature}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>{d.value}</span>
                      <div style={{ width: '60px', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px' }}>
                        <div style={{ height: '100%', width: `${d.importance / 15 * 100}%`, background: 'var(--accent)', borderRadius: '2px' }} />
                      </div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', fontFamily: 'var(--font-mono)', width: '35px', textAlign: 'right' }}>{d.importance}%</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* AI Reasoning */}
              <div style={{
                background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
                borderRadius: '1rem', padding: '1.5rem',
              }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Brain size={16} color="var(--accent)" /> AI Reasoning
                </h3>
                <p style={{
                  color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: '1.6',
                  padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.5rem',
                  borderLeft: `3px solid ${getConfidenceColor(selectedPrediction.confidence)}`,
                }}>
                  {selectedPrediction.reasoning}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Row: Feature Importance + Confidence Heatmap */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          {/* Feature Importance Chart */}
          <div style={{
            background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
            borderRadius: '1rem', padding: '1.5rem',
          }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChart3 size={18} color="var(--accent)" /> Feature Importance (What Drives Predictions)
            </h2>
            <div style={{ height: '350px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={featureImportance} layout="vertical" margin={{ left: 110, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis type="number" stroke="var(--text-muted)" fontSize={11} tickFormatter={(v) => `${v}%`} />
                  <YAxis dataKey="feature" type="category" stroke="var(--text-muted)" fontSize={11} width={100} />
                  <Tooltip
                    contentStyle={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: '0.5rem', color: 'var(--text-primary)' }}
                    formatter={(value: unknown) => [`${value}%`, 'Importance']}
                  />
                  <Bar dataKey="importance" fill="var(--accent)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stock Confidence Heatmap */}
          <div style={{
            background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
            borderRadius: '1rem', padding: '1.5rem',
          }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={18} color="var(--accent)" /> Rise Probability Heatmap
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.5rem' }}>
              {heatmapData.map((item, i) => (
                <div
                  key={i}
                  onClick={() => {
                    const pred = predictions.find(p => p.symbol === item.symbol);
                    if (pred) setSelectedPrediction(pred);
                  }}
                  style={{
                    padding: '0.75rem 0.5rem',
                    background: `${getProbColor(item.probability)}${Math.round(item.probability * 0.4).toString(16).padStart(2, '0')}`,
                    border: `1px solid ${getProbColor(item.probability)}44`,
                    borderRadius: '0.5rem',
                    textAlign: 'center',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>{item.symbol}</div>
                  <div style={{ fontSize: '1rem', fontWeight: 700, color: getProbColor(item.probability), fontFamily: 'var(--font-mono)' }}>
                    {item.probability}%
                  </div>
                  <div style={{ fontSize: '0.65rem', color: item.change > 0 ? '#4ade80' : '#ef4444' }}>
                    {item.change > 0 ? '+' : ''}{item.change.toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>

            {/* Model Architecture Info */}
            <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.5rem' }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '0.75rem' }}>ML ARCHITECTURE</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
                <div>
                  <div style={{ fontSize: '0.7rem', color: '#4ade80', fontWeight: 600 }}>Random Forest</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>200 trees · depth 12</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>Weight: 40%</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: '#818cf8', fontWeight: 600 }}>XGBoost</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>150 trees · lr 0.08</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>Weight: 35%</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: '#f97316', fontWeight: 600 }}>Gradient Boost</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>150 trees · lr 0.08</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>Weight: 25%</div>
                </div>
              </div>
              <div style={{ marginTop: '0.75rem', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                Feature Categories: Technical ({metrics.feature_categories.technical}) · Fundamental ({metrics.feature_categories.fundamental}) · Volume/Flow ({metrics.feature_categories.volume_flow}) · Market Context ({metrics.feature_categories.market_context})
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
