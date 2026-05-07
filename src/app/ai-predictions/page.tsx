'use client';

import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Brain, Cpu, Database, Target, TrendingUp, Zap } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import { ApiDataSource, fetchAIPredictions } from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;
const PROB_COLORS = ['#ef4444', '#f97316', '#facc15', '#a3e635', '#4ade80', '#00ff88'];

type AIPrediction = {
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
  recommendationSummary: string;
  keyDrivers: { feature: string; value: number; direction: string; importance: number }[];
  reasoning: string;
  modelScores: { randomForest: number; xgboost: number; mlpClassifier: number; gradientBoosting: number; mlpRegressor: number };
  buyRangeLow: number;
  buyRangeHigh: number;
  idealEntry: number;
  stopLoss: number;
  sellRangeLow: number;
  sellRangeHigh: number;
  expectedProfitRs: number;
  expectedProfitPercent: number;
  expectedDownsideRs: number;
  expectedDownsidePercent: number;
  riskRewardRatio: number;
  holdDaysMin: number;
  holdDaysMax: number;
  timeToTargetDays: number;
  marketAlignment: string;
  crashRisk: number;
  exitTrigger: string;
};

type AIPredictionsResponse = {
  predictions: AIPrediction[];
  totalStocks: number;
  dataSource: ApiDataSource;
  timestamp?: string;
  marketRegime?: string;
  marketIntelligence?: {
    bias: string;
    crash_risk: number;
    crash_level: string;
    action: string;
    trend_score: number;
    warnings: Array<{ title: string; message: string }>;
  };
  modelMetrics: {
    accuracy: number;
    samples: number;
    features: number;
    training_time: number;
    features_used: number;
  };
  featureImportance: { feature: string; importance: number }[];
};

function getProbColor(probability: number): string {
  if (probability >= 75) return PROB_COLORS[5];
  if (probability >= 65) return PROB_COLORS[4];
  if (probability >= 55) return PROB_COLORS[3];
  if (probability >= 45) return PROB_COLORS[2];
  if (probability >= 35) return PROB_COLORS[1];
  return PROB_COLORS[0];
}

function getConfidenceColor(confidence: string): string {
  switch (confidence) {
    case 'VERY HIGH':
      return '#00ff88';
    case 'HIGH':
      return '#4ade80';
    case 'MEDIUM':
      return '#facc15';
    default:
      return '#ef4444';
  }
}

function getActionColor(action: string): string {
  switch (action) {
    case 'STRONG BUY':
      return '#00ff88';
    case 'BUY':
      return '#4ade80';
    case 'SPECULATIVE BUY':
      return '#facc15';
    case 'HOLD':
      return '#94a3b8';
    default:
      return '#ef4444';
  }
}

function formatSource(source: ApiDataSource): string {
  switch (source) {
    case 'LIVE':
      return 'NEPSE API';
    case 'LIVE_SCRAPED':
      return 'Sharesansar';
    case 'LIVE_SCRAPED_MEROLAGANI':
      return 'Merolagani';
    case 'UNAVAILABLE':
      return 'Unavailable';
    default:
      return 'Unknown';
  }
}

export default function AIPredictionsPage() {
  const [data, setData] = useState<AIPredictionsResponse | null>(null);
  const [selected, setSelected] = useState<AIPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadAiPredictions() {
      try {
        const response = await fetchAIPredictions(15) as AIPredictionsResponse;
        if (!isActive) {
          return;
        }

        setData(response);
        setSelected(response.predictions[0] ?? null);
        setError(null);
      } catch (loadError) {
        if (!isActive) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load AI predictions.');
      }
    }

    loadAiPredictions();
    const interval = window.setInterval(loadAiPredictions, REFRESH_INTERVAL_MS);

    return () => {
      isActive = false;
      window.clearInterval(interval);
    };
  }, []);

  const predictions = data?.predictions ?? [];
  const topPicks = predictions.filter((prediction) => prediction.predictedChangePercent > 0).slice(0, 10);
  const featureData = data?.featureImportance?.slice(0, 8) ?? [];
  const confidenceData = [
    { name: 'Bullish', value: predictions.filter((prediction) => prediction.riseProbability >= 65).length },
    { name: 'Watchlist', value: predictions.filter((prediction) => prediction.riseProbability >= 50 && prediction.riseProbability < 65).length },
    { name: 'Avoid', value: predictions.filter((prediction) => prediction.riseProbability < 50).length },
  ];

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
            <Brain size={32} color="var(--accent)" />
          <h1 style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              AI Recommendation Engine
            </h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Backend recommendation engine using tree ensembles plus neural nets. Outputs are probabilistic trade plans, not guaranteed outcomes.
          </p>
          <div style={{
            display: 'inline-flex', gap: '0.5rem', padding: '0.4rem 1rem',
            background: 'rgba(0,255,136,0.1)',
            border: '1px solid rgba(0,255,136,0.3)',
            borderRadius: '2rem',
            color: '#00ff88',
            fontSize: '0.8rem', fontFamily: 'var(--font-mono)',
          }}>
            <Cpu size={14} /> {formatSource(data?.dataSource ?? 'UNKNOWN')} · refresh {REFRESH_INTERVAL_MS / 1000}s · {data?.totalStocks ?? 0} stocks
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
          {[
            { label: 'MODEL ACCURACY', value: `${data?.modelMetrics?.accuracy?.toFixed(1) ?? '--'}%`, sub: `${data?.modelMetrics?.samples ?? '--'} samples`, icon: Target, color: '#00ff88' },
            { label: 'FEATURES USED', value: `${data?.modelMetrics?.features_used ?? data?.modelMetrics?.features ?? '--'}`, sub: 'Current feature set', icon: Database, color: '#818cf8' },
            { label: 'TRAINING TIME', value: `${data?.modelMetrics?.training_time?.toFixed(2) ?? '--'}s`, sub: 'Snapshot-triggered retrain', icon: Zap, color: '#facc15' },
            {
              label: 'MARKET RISK',
              value: `${data?.marketIntelligence?.crash_risk?.toFixed(0) ?? '--'}%`,
              sub: `${data?.marketIntelligence?.crash_level ?? '--'} · ${data?.marketRegime ?? 'Unknown'}`,
              icon: TrendingUp,
              color: (data?.marketIntelligence?.crash_risk ?? 0) >= 60 ? '#ef4444' : '#4ade80',
            },
          ].map((stat) => (
            <div key={stat.label} style={{
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

        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '1.5rem', marginBottom: '2rem' }}>
          <div style={{
            background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
            borderRadius: '1rem', padding: '1.5rem',
          }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Top AI Picks</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: 620, overflowY: 'auto' }}>
              {topPicks.map((prediction) => (
                <div
                  key={prediction.symbol}
                  onClick={() => setSelected(prediction)}
                  style={{
                    padding: '1rem 1.25rem',
                    background: selected?.symbol === prediction.symbol ? 'rgba(0,255,136,0.08)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${selected?.symbol === prediction.symbol ? 'rgba(0,255,136,0.3)' : 'var(--glass-border)'}`,
                    borderRadius: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <div>
                      <div style={{ fontSize: '1rem', fontWeight: 700 }}>{prediction.symbol}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{prediction.sector}</div>
                    </div>
                    <span style={{
                      padding: '0.2rem 0.6rem',
                      borderRadius: '0.3rem',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      background: `${getActionColor(prediction.action)}22`,
                      color: getActionColor(prediction.action),
                      border: `1px solid ${getActionColor(prediction.action)}44`,
                    }}>
                      {prediction.action}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>RISE PROB</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 700, color: getProbColor(prediction.riseProbability), fontFamily: 'var(--font-mono)' }}>
                        {prediction.riseProbability}%
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>TARGET</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#4ade80', fontFamily: 'var(--font-mono)' }}>
                        Rs.{prediction.predictedTarget.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>BUY RANGE</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: prediction.predictedRsChange > 0 ? '#4ade80' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
                        Rs.{prediction.buyRangeLow.toLocaleString()}-{Math.round(prediction.buyRangeHigh)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>HOLD</div>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: getConfidenceColor(prediction.confidence) }}>{prediction.holdDaysMin}-{prediction.holdDaysMax}d</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{
              background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
              borderRadius: '1rem', padding: '1.5rem',
            }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem' }}>Feature Importance</h3>
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                  <BarChart data={featureData} layout="vertical">
                    <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.04)" />
                    <XAxis type="number" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                    <YAxis type="category" dataKey="feature" width={110} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#8b95b0', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                    <Bar dataKey="importance" fill="#6366f1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div style={{
              background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
              borderRadius: '1rem', padding: '1.5rem',
            }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem' }}>Prediction Mix</h3>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                  <PieChart>
                    <Pie data={confidenceData} dataKey="value" innerRadius={55} outerRadius={85} paddingAngle={3}>
                      {confidenceData.map((entry) => (
                        <Cell key={entry.name} fill={entry.name === 'Bullish' ? '#00ff88' : entry.name === 'Watchlist' ? '#facc15' : '#ef4444'} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>

        {selected ? (
          <div style={{
            background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
            borderRadius: '1rem', padding: '1.5rem',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{selected.symbol}</h2>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '2rem',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: `${getActionColor(selected.action)}22`,
                    color: getActionColor(selected.action),
                    border: `1px solid ${getActionColor(selected.action)}44`,
                  }}>
                    {selected.action}
                  </span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                  {selected.name} · {selected.sector}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: getProbColor(selected.riseProbability), fontFamily: 'var(--font-mono)' }}>
                  {selected.riseProbability}%
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>RISE PROBABILITY</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
              {[
                { label: 'CMP', value: `Rs.${selected.cmp.toLocaleString()}`, sub: `${selected.changePercent >= 0 ? '+' : ''}${selected.changePercent}%`, color: selected.changePercent >= 0 ? '#4ade80' : '#ef4444' },
                { label: 'BUY RANGE', value: `Rs.${selected.buyRangeLow.toLocaleString()}-${Math.round(selected.buyRangeHigh)}`, sub: `Ideal Rs.${selected.idealEntry.toLocaleString()}`, color: '#4ade80' },
                { label: 'SELL RANGE', value: `Rs.${selected.sellRangeLow.toLocaleString()}-${Math.round(selected.sellRangeHigh)}`, sub: `${selected.expectedProfitPercent.toFixed(1)}% upside`, color: '#00ff88' },
                { label: 'RISK / REWARD', value: `${selected.riskRewardRatio.toFixed(2)}x`, sub: `${selected.expectedDownsidePercent.toFixed(1)}% downside`, color: selected.riskRewardRatio >= 1.8 ? '#4ade80' : '#facc15' },
                { label: 'HOLD', value: `${selected.holdDaysMin}-${selected.holdDaysMax} days`, sub: `ETA ${selected.timeToTargetDays}d`, color: selected.risk === 'LOW' ? '#4ade80' : selected.risk === 'MODERATE' ? '#facc15' : '#ef4444' },
              ].map((item) => (
                <div key={item.label} style={{ textAlign: 'center', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.5rem' }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '0.25rem' }}>{item.label}</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: item.color, fontFamily: 'var(--font-mono)' }}>{item.value}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>{item.sub}</div>
                </div>
              ))}
            </div>

            <div style={{ marginBottom: '1rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {selected.reasoning}
            </div>

            <div style={{ marginBottom: '1rem', padding: '1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {selected.recommendationSummary}
              <div style={{ marginTop: 10, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Stop-loss Rs.{selected.stopLoss.toLocaleString()} · {selected.marketAlignment} market alignment · crash risk {selected.crashRisk.toFixed(0)}%
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
              {[
                { label: 'EXIT TRIGGER', value: selected.exitTrigger, color: '#f97316' },
                { label: 'MODEL STACK', value: `RF ${selected.modelScores.randomForest}% · XGB ${selected.modelScores.xgboost}% · MLP ${selected.modelScores.mlpClassifier}%`, color: '#818cf8' },
                { label: 'EXPECTED P&L', value: `+Rs.${Math.round(selected.expectedProfitRs)} / -Rs.${Math.round(selected.expectedDownsideRs)}`, color: '#4ade80' },
              ].map((item) => (
                <div key={item.label} style={{ padding: '0.85rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.75rem', border: '1px solid var(--glass-border)' }}>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6 }}>{item.label}</div>
                  <div style={{ fontSize: '0.88rem', lineHeight: 1.5, color: item.color }}>{item.value}</div>
                </div>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.75rem' }}>
              {selected.keyDrivers.map((driver) => (
                <div key={driver.feature} style={{ padding: '0.85rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.75rem', border: '1px solid var(--glass-border)' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 6 }}>{driver.feature}</div>
                  <div style={{ fontSize: '1rem', fontWeight: 700 }}>
                    {driver.direction} {driver.value}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
                    importance {driver.importance}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}
