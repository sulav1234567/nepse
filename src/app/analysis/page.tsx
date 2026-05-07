'use client';

import { Suspense, startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts';

import Sidebar from '@/components/Sidebar';
import CandlestickChart from '@/components/CandlestickChart';
import {
  ApiHistoryCandle,
  ApiStockAnalysis,
  fetchLiveStocks,
  fetchStockAnalysis,
  fetchStockHistory,
} from '@/lib/api-client';

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

function formatCurrency(value: number): string {
  return `Rs.${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function AnalysisContent() {
  const searchParams = useSearchParams();
  const symbolParam = searchParams.get('symbol');
  const [options, setOptions] = useState<Array<{ symbol: string; name: string }>>([]);
  const [selectedSymbol, setSelectedSymbol] = useState(symbolParam ?? '');
  const [analysis, setAnalysis] = useState<ApiStockAnalysis | null>(null);
  const [history, setHistory] = useState<ApiHistoryCandle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const deferredSymbol = useDeferredValue(selectedSymbol);

  useEffect(() => {
    if (symbolParam && symbolParam !== selectedSymbol) {
      setSelectedSymbol(symbolParam);
    }
  }, [selectedSymbol, symbolParam]);

  useEffect(() => {
    let active = true;

    async function loadStocks() {
      try {
        const response = await fetchLiveStocks();
        if (!active) {
          return;
        }

        const nextOptions = response.stocks.map((stock) => ({
          symbol: stock.symbol,
          name: stock.name,
        }));
        setOptions(nextOptions);

        if (!selectedSymbol && nextOptions.length > 0) {
          setSelectedSymbol(symbolParam || nextOptions[0].symbol);
        }
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load stock universe.');
      }
    }

    loadStocks();
    return () => {
      active = false;
    };
  }, [selectedSymbol, symbolParam]);

  useEffect(() => {
    if (!deferredSymbol) {
      return;
    }

    let active = true;

    async function loadAnalysis() {
      setLoading(true);
      try {
        const [analysisResponse, historyResponse] = await Promise.all([
          fetchStockAnalysis(deferredSymbol),
          fetchStockHistory(deferredSymbol),
        ]);

        if (!active) {
          return;
        }

        setAnalysis(analysisResponse);
        setHistory(historyResponse);
        setError(null);
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load stock analysis.');
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadAnalysis();
    return () => {
      active = false;
    };
  }, [deferredSymbol]);

  const radarData = useMemo(() => {
    if (!analysis) {
      return [];
    }

    return [
      { layer: 'FVL', score: analysis.fcs.layer_scores.fvl },
      { layer: 'TML', score: analysis.fcs.layer_scores.tml },
      { layer: 'SSIL', score: analysis.fcs.layer_scores.ssil },
      { layer: 'GTBIL', score: analysis.fcs.layer_scores.gtbil },
      { layer: 'MRLLL', score: analysis.fcs.layer_scores.mrlll },
    ];
  }, [analysis]);

  if (loading && !analysis) {
    return <div style={{ padding: 40 }}><div className="loading-skeleton" style={{ height: 480, borderRadius: 16 }} /></div>;
  }

  if (!analysis) {
    return (
      <div style={{ padding: 40 }}>
        <div className="glass-card" style={{ color: 'var(--bearish)' }}>
          {error ?? 'No analysis data available.'}
        </div>
      </div>
    );
  }

  const a = analysis;
  const recommendation = a.recommendation;
  const candles = history.slice(-36);
  const lastCandle = candles[candles.length - 1];

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h2>{a.stock.symbol}</h2>
              <span className={`signal-badge ${getSignalClass(a.fcs.signal)}`} style={{ fontSize: '0.8rem' }}>
                {a.fcs.signal}
              </span>
            </div>
            <div className="subtitle">{a.stock.name} · {a.stock.sector}</div>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 240 }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>SELECT STOCK</span>
            <select
              value={selectedSymbol}
              onChange={(event) => {
                const value = event.target.value;
                startTransition(() => setSelectedSymbol(value));
              }}
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid var(--glass-border)',
                color: 'var(--text-primary)',
                borderRadius: '0.85rem',
                padding: '0.8rem 1rem',
              }}
            >
              {options.map((option) => (
                <option key={option.symbol} value={option.symbol}>
                  {option.symbol} · {option.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="data-badge live" style={{ marginTop: 14 }}>
          <span className="pulse"></span>
          LIVE SESSION CANDLE + BACKEND ANALYSIS
        </div>
      </div>

      {error ? (
        <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
          {error}
        </div>
      ) : null}

      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        {[
          {
            label: 'CMP',
            value: formatCurrency(a.stock.cmp),
            sub: `${a.stock.change_percent >= 0 ? '+' : ''}${a.stock.change_percent.toFixed(2)}%`,
            color: a.stock.change_percent >= 0 ? 'var(--bullish)' : 'var(--bearish)',
          },
          {
            label: 'BSTS FAIR',
            value: formatCurrency(a.bsts_fair_value),
            sub: `${a.overvaluation_percent > 0 ? '+' : ''}${a.overvaluation_percent.toFixed(1)}% vs fair`,
            color: a.overvaluation_percent <= 0 ? 'var(--bullish)' : 'var(--bearish)',
          },
          {
            label: 'PT1',
            value: formatCurrency(a.price_targets.pt1),
            sub: 'First objective',
            color: 'var(--bullish)',
          },
          {
            label: 'SELL ZONE',
            value: recommendation ? `${formatCurrency(recommendation.sell_zone_low)}-${formatCurrency(recommendation.sell_zone_high)}` : '--',
            sub: recommendation ? `${recommendation.hold_days_min}-${recommendation.hold_days_max} sessions` : 'Waiting',
            color: 'var(--accent-primary)',
          },
          {
            label: 'STOP',
            value: recommendation ? formatCurrency(recommendation.stop_loss) : formatCurrency(a.price_targets.stop_loss),
            sub: recommendation ? `${recommendation.expected_downside_percent.toFixed(1)}% downside` : 'Risk limit',
            color: 'var(--bearish)',
          },
          {
            label: 'FCS',
            value: Math.round(a.fcs.score).toString(),
            sub: a.fcs.signal,
            color: a.fcs.score >= 70 ? 'var(--bullish)' : a.fcs.score >= 50 ? 'var(--hold)' : 'var(--bearish)',
          },
        ].map((stat) => (
          <div key={stat.label} className="stat-card">
            <div className="stat-label">{stat.label}</div>
            <div className="stat-value" style={{ fontSize: '1.1rem', color: stat.color }}>{stat.value}</div>
            <div className="stat-change">{stat.sub}</div>
          </div>
        ))}
      </div>

      <div className="dashboard-grid grid-2" style={{ margin: '24px 0', alignItems: 'start' }}>
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Candlestick Setup</div>
          </div>
          <CandlestickChart
            data={candles}
            guides={[
              { label: 'Target', value: a.price_targets.pt1, color: '#1dd1a1' },
              { label: 'Stop', value: recommendation?.stop_loss ?? a.price_targets.stop_loss, color: '#ef4444' },
            ]}
          />

          {lastCandle ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginTop: 18 }}>
              {[
                { label: 'OPEN', value: formatCurrency(lastCandle.open) },
                { label: 'HIGH', value: formatCurrency(lastCandle.high) },
                { label: 'LOW', value: formatCurrency(lastCandle.low) },
                { label: 'CLOSE', value: formatCurrency(lastCandle.close) },
                { label: 'VOLUME', value: lastCandle.volume.toLocaleString() },
              ].map((item) => (
                <div key={item.label} style={{ padding: '0.8rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                  <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 6 }}>{item.label}</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700 }}>{item.value}</div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">AI Trade Plan</div>
          </div>

          {recommendation ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 18 }}>
                <div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{recommendation.action}</div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 4 }}>{recommendation.confidence} conviction</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--bullish)', fontFamily: 'var(--font-mono)' }}>
                    {recommendation.expected_upside_percent.toFixed(1)}%
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>expected upside</div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 18 }}>
                {[
                  { label: 'BUY RANGE', value: `${formatCurrency(recommendation.entry_low)}-${formatCurrency(recommendation.entry_high)}`, sub: `Ideal ${formatCurrency(recommendation.ideal_entry)}` },
                  { label: 'SELL RANGE', value: `${formatCurrency(recommendation.sell_zone_low)}-${formatCurrency(recommendation.sell_zone_high)}`, sub: `PT2 ${formatCurrency(recommendation.take_profit_2)}` },
                  { label: 'HOLD WINDOW', value: `${recommendation.hold_days_min}-${recommendation.hold_days_max} sessions`, sub: `ETA ${recommendation.time_to_target_days} sessions` },
                  { label: 'RISK / REWARD', value: `${recommendation.risk_reward_ratio.toFixed(2)}x`, sub: `${recommendation.expected_downside_percent.toFixed(1)}% downside` },
                ].map((item) => (
                  <div key={item.label} style={{ padding: '0.95rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                    <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 6 }}>{item.label}</div>
                    <div style={{ fontSize: '0.96rem', fontWeight: 700 }}>{item.value}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: 5 }}>{item.sub}</div>
                  </div>
                ))}
              </div>

              <div style={{ marginBottom: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {recommendation.thesis}
              </div>

              <div style={{ padding: '0.95rem 1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', marginBottom: 14 }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 6 }}>EXIT TRIGGER</div>
                <div style={{ color: 'var(--text-secondary)', lineHeight: 1.55 }}>{recommendation.exit_trigger}</div>
              </div>

              <div style={{ display: 'grid', gap: 10 }}>
                {recommendation.notes.map((note) => (
                  <div key={note} style={{ padding: '0.85rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)', color: 'var(--text-secondary)' }}>
                    {note}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--text-secondary)' }}>Recommendation plan unavailable for this symbol.</div>
          )}
        </div>
      </div>

      <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Five-Layer Radar</div>
          </div>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis dataKey="layer" tick={{ fill: '#8b95b0', fontSize: 12, fontWeight: 700 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#5a6580', fontSize: 9 }} />
                <Radar name="Score" dataKey="score" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.22} strokeWidth={2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Candlestick Analysis</div>
          </div>
          <div style={{ display: 'grid', gap: 12 }}>
            {(a.candlestick_patterns.length ? a.candlestick_patterns : [{
              name: 'No dominant pattern',
              sentiment: 'NEUTRAL' as const,
              strength: 40,
              explanation: 'The latest candles are mixed, so price structure is being interpreted mainly through trend, momentum, and volume.',
            }]).map((pattern) => (
              <div key={pattern.name} style={{ padding: '1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                  <div style={{ fontWeight: 700 }}>{pattern.name}</div>
                  <div style={{ color: pattern.sentiment === 'BULLISH' ? 'var(--bullish)' : pattern.sentiment === 'BEARISH' ? 'var(--bearish)' : 'var(--text-secondary)' }}>
                    {pattern.sentiment} · {pattern.strength.toFixed(0)}/100
                  </div>
                </div>
                <div style={{ color: 'var(--text-secondary)', lineHeight: 1.55 }}>{pattern.explanation}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Risk Flags</div>
          </div>
          <div className="warning-panel">
            {[
              ['SIS Score', `${Math.round(a.warning_flags.sis_score)} · ${a.warning_flags.sis_level}`],
              ['BMR', `${Math.round(a.warning_flags.bmr)}% · ${a.warning_flags.bmr_level}`],
              ['TTH Status', a.warning_flags.tth_status],
              ['Political Risk', a.warning_flags.political_risk],
              ['BSTS Confidence', a.warning_flags.bsts_confidence],
              ['Circular Trading', a.warning_flags.circular_trading ? 'DETECTED' : 'None'],
            ].map(([label, value]) => (
              <div key={label} className="warning-item">
                <div className="warning-label">{label}</div>
                <div className="warning-value safe">{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Override Conditions</div>
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {a.fcs.overrides.map((override) => (
              <div key={override.id} className="warning-item" style={{ borderColor: override.triggered ? 'rgba(239,68,68,0.45)' : 'var(--border-subtle)' }}>
                <div className="warning-label">{override.name}</div>
                <div className={`warning-value ${override.triggered ? 'danger' : 'safe'}`}>
                  {override.triggered ? 'TRIGGERED' : 'Clear'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
        {[
          { title: 'Fundamental Value Layer', details: a.fvl_details, color: '#818cf8' },
          { title: 'Technical Momentum Layer', details: a.tml_details, color: '#38bdf8' },
          { title: 'Social Sentiment Layer', details: a.ssil_details, color: '#f59e0b' },
          { title: 'Broker / Flow Layer', details: a.gtbil_details, color: '#18c47c' },
        ].map((section) => (
          <div className="glass-card" key={section.title}>
            <div className="glass-card-header">
              <div className="glass-card-title" style={{ color: section.color }}>{section.title}</div>
            </div>
            <ul className="detail-list">
              {section.details.map((detail) => <li key={detail}>{detail}</li>)}
            </ul>
          </div>
        ))}
      </div>

      <div className="glass-card">
        <div className="glass-card-header">
          <div className="glass-card-title">Retail vs Institutional Verdict</div>
        </div>
        <div className="verdict-box">{a.retail_institutional_verdict}</div>
      </div>
    </>
  );
}

export default function AnalysisPage() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Suspense fallback={<div style={{ padding: 40 }}><div className="loading-skeleton" style={{ height: 480, borderRadius: 16 }} /></div>}>
          <AnalysisContent />
        </Suspense>
      </main>
    </div>
  );
}
