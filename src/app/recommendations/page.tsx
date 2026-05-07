'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BrainCircuit, ShieldCheck, Sparkles, Target } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import { ApiDataSource, ApiMarketIntelligence, fetchAIPredictions, fetchMarketIntelligence } from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

type RecommendationPrediction = {
  rank: number;
  symbol: string;
  name: string;
  sector: string;
  riseProbability: number;
  predictedTarget: number;
  action: string;
  confidence: string;
  risk: string;
  buyRangeLow: number;
  buyRangeHigh: number;
  idealEntry: number;
  sellRangeLow: number;
  sellRangeHigh: number;
  stopLoss: number;
  holdDaysMin: number;
  holdDaysMax: number;
  expectedProfitPercent: number;
  expectedProfitRs: number;
  expectedDownsidePercent: number;
  riskRewardRatio: number;
  recommendationSummary: string;
  reasoning: string;
  exitTrigger: string;
  marketAlignment: string;
  crashRisk: number;
};

type RecommendationsResponse = {
  predictions: RecommendationPrediction[];
  totalStocks: number;
  dataSource: ApiDataSource;
  marketRegime?: string;
  marketIntelligence?: ApiMarketIntelligence;
  timestamp?: string;
};

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

function getAdvice(prediction: RecommendationPrediction, market: ApiMarketIntelligence | null): string[] {
  const notes: string[] = [];
  if (prediction.marketAlignment === 'HEADWIND' || (market?.crash_risk ?? 0) >= 55) {
    notes.push('Use smaller sizing and staggered entries because the market backdrop is fighting the setup.');
  } else {
    notes.push('The broader market is not heavily hostile, so planned pullback entries are more reasonable than panic chasing.');
  }

  if (prediction.riskRewardRatio >= 1.8) {
    notes.push('Reward-to-risk is healthy enough to justify attention if the buy range is respected.');
  } else {
    notes.push('Reward-to-risk is only moderate, so wait for cleaner pullbacks instead of forcing a full-size entry.');
  }

  if (prediction.riseProbability >= 70 && prediction.confidence !== 'LOW') {
    notes.push('This setup suits active traders who can monitor exits and adjust once the first target zone is reached.');
  } else {
    notes.push('Treat this as watchlist-quality unless price improves inside the suggested buy band and the market stays stable.');
  }

  notes.push(`Invalidation: ${prediction.exitTrigger}`);
  return notes;
}

export default function RecommendationsPage() {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [market, setMarket] = useState<ApiMarketIntelligence | null>(null);
  const [selected, setSelected] = useState<RecommendationPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const [recommendations, marketResponse] = await Promise.all([
          fetchAIPredictions(20) as Promise<RecommendationsResponse>,
          fetchMarketIntelligence(),
        ]);

        if (!active) {
          return;
        }

        const actionable = recommendations.predictions.filter((prediction) => prediction.action !== 'AVOID');
        setData(recommendations);
        setMarket(marketResponse.intelligence);
        setSelected(actionable[0] ?? recommendations.predictions[0] ?? null);
        setError(null);
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load recommendation engine.');
      }
    }

    loadData();
    const interval = window.setInterval(loadData, REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const picks = useMemo(() => (data?.predictions ?? []).filter((prediction) => prediction.action !== 'AVOID').slice(0, 12), [data]);
  const counseling = selected ? getAdvice(selected, market) : [];

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Recommendation & Counseling Engine</h2>
          <div className="subtitle">Live trade plans with buy range, sell range, hold window, and market-aware counseling.</div>
          <div className={`data-badge ${data?.dataSource === 'UNAVAILABLE' ? 'demo' : 'live'}`}>
            <span className="pulse"></span>
            {formatSource(data?.dataSource ?? 'UNKNOWN')} · {data?.marketRegime ?? 'Scanning'} · {data?.totalStocks ?? 0} stocks
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.75rem' }}>
          {[
            { label: 'ACTIONABLE IDEAS', value: picks.length, sub: 'Current top live candidates', icon: Sparkles, color: '#00ff88' },
            { label: 'MARKET BIAS', value: market?.bias ?? '--', sub: market?.action ?? 'Waiting', icon: BrainCircuit, color: '#38bdf8' },
            { label: 'CRASH RISK', value: `${market?.crash_risk?.toFixed(0) ?? '--'}%`, sub: market?.crash_level ?? 'Waiting', icon: AlertTriangle, color: (market?.crash_risk ?? 0) >= 60 ? '#ef4444' : '#facc15' },
            { label: 'BULL PROB', value: `${market?.bull_probability?.toFixed(0) ?? '--'}%`, sub: 'Main market stance', icon: Target, color: '#4ade80' },
          ].map((item) => (
            <div key={item.label} className="glass-card" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{item.label}</div>
                  <div style={{ fontSize: '1.55rem', fontWeight: 700, color: item.color, marginTop: 8 }}>{item.value}</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: 6 }}>{item.sub}</div>
                </div>
                <item.icon size={22} color={item.color} style={{ opacity: 0.65 }} />
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.02fr 0.98fr', gap: '1.25rem' }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Live Recommendation Queue</div>
            </div>
            <div style={{ display: 'grid', gap: 12 }}>
              {picks.map((prediction) => (
                <button
                  key={prediction.symbol}
                  type="button"
                  onClick={() => setSelected(prediction)}
                  style={{
                    textAlign: 'left',
                    padding: '1rem 1.1rem',
                    borderRadius: '0.95rem',
                    border: `1px solid ${selected?.symbol === prediction.symbol ? 'rgba(0,255,136,0.32)' : 'var(--glass-border)'}`,
                    background: selected?.symbol === prediction.symbol ? 'rgba(0,255,136,0.08)' : 'rgba(255,255,255,0.02)',
                    color: 'inherit',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '1rem' }}>{prediction.symbol}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{prediction.name} · {prediction.sector}</div>
                    </div>
                    <div style={{ color: '#00ff88', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{prediction.riseProbability.toFixed(1)}%</div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                    {[
                      ['BUY', `Rs.${prediction.buyRangeLow.toLocaleString()}-${Math.round(prediction.buyRangeHigh)}`],
                      ['SELL', `Rs.${prediction.sellRangeLow.toLocaleString()}-${Math.round(prediction.sellRangeHigh)}`],
                      ['HOLD', `${prediction.holdDaysMin}-${prediction.holdDaysMax}d`],
                      ['RR', `${prediction.riskRewardRatio.toFixed(2)}x`],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>{label}</div>
                        <div style={{ fontSize: '0.86rem', fontWeight: 600 }}>{value}</div>
                      </div>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Counseling View</div>
            </div>

            {selected ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 18 }}>
                  <div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{selected.symbol}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{selected.action} · {selected.confidence} confidence · {selected.risk} risk</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '1.65rem', fontWeight: 700, color: '#00ff88', fontFamily: 'var(--font-mono)' }}>
                      {selected.expectedProfitPercent.toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>projected upside</div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 16 }}>
                  {[
                    ['Ideal entry', `Rs.${selected.idealEntry.toLocaleString()}`],
                    ['Stop-loss', `Rs.${selected.stopLoss.toLocaleString()}`],
                    ['Expected profit', `+Rs.${Math.round(selected.expectedProfitRs)}`],
                    ['Expected downside', `-${selected.expectedDownsidePercent.toFixed(1)}%`],
                  ].map(([label, value]) => (
                    <div key={label} style={{ padding: '0.95rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{label}</div>
                      <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: 8 }}>{value}</div>
                    </div>
                  ))}
                </div>

                <div style={{ padding: '1rem 1.05rem', borderRadius: '0.95rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
                  {selected.recommendationSummary}
                </div>

                <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
                  {counseling.map((note) => (
                    <div key={note} style={{ padding: '0.95rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', color: 'var(--text-secondary)' }}>
                      {note}
                    </div>
                  ))}
                </div>

                <div style={{ padding: '1rem 1.05rem', borderRadius: '0.95rem', background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.16)', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
                  {selected.reasoning}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#94f1c1' }}>
                  <ShieldCheck size={18} />
                  <span>Market alignment: {selected.marketAlignment} · live crash risk {selected.crashRisk.toFixed(0)}%</span>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-secondary)' }}>No recommendation selected yet.</div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
