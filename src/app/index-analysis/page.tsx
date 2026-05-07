'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, CandlestickChart as CandleIcon, ShieldAlert } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import CandlestickChart from '@/components/CandlestickChart';
import { ApiIndexAnalysisResponse, fetchNepseIndexAnalysis } from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

function normalizeNumber(value: number | null | undefined, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function formatCurrency(value: number | null | undefined): string {
  return `Rs.${normalizeNumber(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatFixed(value: number | null | undefined, digits = 2): string {
  return normalizeNumber(value).toFixed(digits);
}

function formatSignedPercent(value: number | null | undefined, digits = 2): string {
  const amount = normalizeNumber(value);
  return `${amount >= 0 ? '+' : ''}${amount.toFixed(digits)}%`;
}

export default function IndexAnalysisPage() {
  const [data, setData] = useState<ApiIndexAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const response = await fetchNepseIndexAnalysis(90);
        if (!active) {
          return;
        }
        setData(response);
        setError(null);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load NEPSE index analysis.');
      } finally {
        if (active) setLoading(false);
      }
    }

    loadData();
    const interval = window.setInterval(loadData, REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const candles = useMemo(
    () => (data?.history ?? []).slice(-40).map((candle) => ({
      date: candle.date,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    })),
    [data],
  );

  const signals = data?.analysis?.signals;
  const close = normalizeNumber(signals?.close);
  const dayChangePercent = normalizeNumber(signals?.day_change_percent);
  const riseProbability = normalizeNumber(signals?.rise_probability);
  const crashProbability = normalizeNumber(signals?.crash_probability);
  const rsi14 = normalizeNumber(signals?.rsi14, 50);
  const trendStrength = normalizeNumber(signals?.trend_strength, 50);
  const macd = normalizeNumber(signals?.macd);
  const bbPct = normalizeNumber(signals?.bb_pct, 50);
  const atrPct = normalizeNumber(signals?.atr_pct);
  const volRatio = normalizeNumber(signals?.vol_ratio, 1);
  const mlAvailable = !!(signals as any)?.ml_available;
  const swing5d = normalizeNumber(signals?.swing_5d);
  const swing20d = normalizeNumber(signals?.swing_20d);
  const ema9 = normalizeNumber(signals?.ema9);
  const ema21 = normalizeNumber(signals?.ema21);
  const ema55 = normalizeNumber(signals?.ema55);
  const support = normalizeNumber(signals?.support);
  const resistance = normalizeNumber(signals?.resistance);
  const volatility = normalizeNumber(signals?.volatility);
  const marketCrashRisk = normalizeNumber(signals?.market_crash_risk);
  const latestDate = signals?.latest_date ?? 'latest session';
  const analysisBias = data?.analysis?.bias ?? 'UNKNOWN';
  const summary = data?.analysis?.summary ?? 'Live index analysis is loading.';
  const patterns = data?.analysis?.patterns ?? [];
  const srcLabel = data?.source === 'LIVE_SCRAPED' ? 'Sharesansar' : data?.source === 'LIVE_SCRAPED_MEROLAGANI' ? 'Merolagani' : data?.source === 'CACHED' ? 'CACHED' : data?.source ?? 'LIVE';
  const warnings = data?.analysis?.warnings ?? [];
  const crashLevel = data?.intelligence?.crash_level ?? 'UNKNOWN';

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>NEPSE Index Candle Engine</h2>
          <div className="subtitle">Live main-index candlestick analysis focused on rise probability, crash probability, support, and resistance.</div>
          <div className={`data-badge ${data?.source === 'UNAVAILABLE' ? 'demo' : data?.source === 'CACHED' ? 'demo' : 'live'}`}>
            <span className="pulse"></span>
            {srcLabel} · {mlAvailable ? 'ML ensemble' : 'heuristic'} · refresh {REFRESH_INTERVAL_MS / 1000}s · {latestDate}
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            ⚠ {error}
          </div>
        ) : null}

        {loading ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem', marginBottom: '1.75rem' }}>
              {[1,2,3,4,5].map((i) => (
                <div key={i} className="loading-skeleton" style={{ height: 110, borderRadius: 16 }} />
              ))}
            </div>
            <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
              <div className="loading-skeleton" style={{ height: 360, borderRadius: 16 }} />
              <div className="loading-skeleton" style={{ height: 360, borderRadius: 16 }} />
            </div>
            <div className="dashboard-grid grid-2">
              <div className="loading-skeleton" style={{ height: 280, borderRadius: 16 }} />
              <div className="loading-skeleton" style={{ height: 280, borderRadius: 16 }} />
            </div>
          </>
        ) : data ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem', marginBottom: '1.75rem' }}>
              {[
                { label: 'NEPSE CLOSE', value: formatCurrency(close), sub: `${formatSignedPercent(dayChangePercent)} day`, icon: CandleIcon, color: '#00ff88' },
                { label: 'RISE PROB', value: `${formatFixed(riseProbability, 0)}%`, sub: analysisBias, icon: BarChart3, color: '#4ade80' },
                { label: 'CRASH PROB', value: `${formatFixed(crashProbability, 0)}%`, sub: `${crashLevel} backdrop`, icon: ShieldAlert, color: crashProbability >= 60 ? '#ef4444' : '#facc15' },
                { label: 'ML STRENGTH', value: `${formatFixed(trendStrength, 0)}%`, sub: `RSI ${formatFixed(rsi14, 1)} · 5d ${formatSignedPercent(swing5d)}`, icon: AlertTriangle, color: trendStrength >= 65 ? '#00ff88' : trendStrength <= 35 ? '#ef4444' : '#facc15' },
                { label: 'SUPPORT / RES.', value: `${Math.round(support)} / ${Math.round(resistance)}`, sub: 'Main index tactical bands', icon: CandleIcon, color: '#a78bfa' },
              ].map((item) => (
                <div key={item.label} className="glass-card" style={{ padding: '1.2rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <div>
                      <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{item.label}</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, color: item.color, marginTop: 8 }}>{item.value}</div>
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: 6 }}>{item.sub}</div>
                    </div>
                    <item.icon size={20} color={item.color} style={{ opacity: 0.7 }} />
                  </div>
                </div>
              ))}
            </div>

            <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Main NEPSE Candles</div>
                </div>
                <CandlestickChart
                  data={candles}
                  guides={[
                    { label: 'Support', value: support, color: '#10b981' },
                    { label: 'Resistance', value: resistance, color: '#ef4444' },
                  ]}
                />
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Index Verdict</div>
                </div>
                <div style={{ padding: '1rem 1.05rem', borderRadius: '0.95rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', color: 'var(--text-secondary)', lineHeight: 1.65, marginBottom: 14 }}>
                  {summary}
                </div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {[
                    `EMA stack: ${formatFixed(ema9)} / ${formatFixed(ema21)} / ${formatFixed(ema55)}`,
                    `MACD: ${formatFixed(macd, 3)}  ·  BB%B: ${formatFixed(bbPct, 1)}%`,
                    `ATR: ${formatFixed(atrPct, 2)}%  ·  Vol ratio: ${formatFixed(volRatio, 2)}x`,
                    `20-day swing: ${formatSignedPercent(swing20d)}  ·  Crash risk: ${formatFixed(marketCrashRisk, 0)}%`,
                  ].map((line) => (
                    <div key={line} style={{ padding: '0.9rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="dashboard-grid grid-2">
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Index Candlestick Patterns</div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {(patterns.length ? patterns : [{
                    name: 'No dominant pattern',
                    sentiment: 'NEUTRAL' as const,
                    strength: 40,
                    explanation: 'The latest index candles are mixed, so directional bias is being inferred more from trend and momentum than from one pattern.',
                  }]).map((pattern) => (
                    <div key={pattern.name} style={{ padding: '1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                        <div style={{ fontWeight: 700 }}>{pattern.name}</div>
                        <div style={{ color: pattern.sentiment === 'BULLISH' ? 'var(--bullish)' : pattern.sentiment === 'BEARISH' ? 'var(--bearish)' : 'var(--text-secondary)' }}>
                          {pattern.sentiment} · {pattern.strength.toFixed(0)}/100
                        </div>
                      </div>
                      <div style={{ marginTop: 8, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{pattern.explanation}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Crash / Rise Warnings</div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {(warnings.length ? warnings : [{
                    title: 'No dominant crash warning',
                    message: 'The current live index candles are not flashing a major crash signal, but the market should still be monitored for breakdowns below support.',
                  }]).map((warning) => (
                    <div key={warning.title} style={{ padding: '1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontWeight: 700, marginBottom: 6 }}>{warning.title}</div>
                      <div style={{ color: 'var(--text-secondary)', lineHeight: 1.55 }}>{warning.message}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="glass-card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No candle data could be loaded. The index history scraper may be temporarily unavailable.
          </div>
        )}
      </main>
    </div>
  );
}
