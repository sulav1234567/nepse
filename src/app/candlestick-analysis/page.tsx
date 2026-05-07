'use client';

import { useEffect, useMemo, useState } from 'react';

import Sidebar from '@/components/Sidebar';
import CandlestickChart from '@/components/CandlestickChart';
import { ApiHistoryCandle, ApiStockAnalysis, fetchLiveStocks, fetchStockAnalysis, fetchStockHistory } from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

function formatCurrency(value: number): string {
  return `Rs.${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export default function CandlestickAnalysisPage() {
  const [symbols, setSymbols] = useState<Array<{ symbol: string; name: string }>>([]);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [analysis, setAnalysis] = useState<ApiStockAnalysis | null>(null);
  const [history, setHistory] = useState<ApiHistoryCandle[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadUniverse() {
      try {
        const response = await fetchLiveStocks();
        if (!active) {
          return;
        }
        const nextSymbols = response.stocks.map((stock) => ({ symbol: stock.symbol, name: stock.name }));
        setSymbols(nextSymbols);
        if (!selectedSymbol && nextSymbols.length > 0) {
          setSelectedSymbol(nextSymbols[0].symbol);
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load live stocks.');
      }
    }

    loadUniverse();
    return () => {
      active = false;
    };
  }, [selectedSymbol]);

  useEffect(() => {
    if (!selectedSymbol) {
      return;
    }

    let active = true;

    async function loadCandles() {
      try {
        const [analysisResponse, historyResponse] = await Promise.all([
          fetchStockAnalysis(selectedSymbol),
          fetchStockHistory(selectedSymbol),
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
        setError(loadError instanceof Error ? loadError.message : 'Unable to load candlestick analysis.');
      }
    }

    loadCandles();
    const interval = window.setInterval(loadCandles, REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [selectedSymbol]);

  const candles = useMemo(() => history.slice(-40), [history]);
  const patterns = analysis?.candlestick_patterns ?? [];
  const recommendation = analysis?.recommendation;

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Stock Candlestick Analysis</h2>
          <div className="subtitle">Live stock candles, pattern recognition, and trade-setup context for individual NEPSE stocks.</div>
          <div className="data-badge live">
            <span className="pulse"></span>
            Refresh {REFRESH_INTERVAL_MS / 1000}s · {selectedSymbol || 'select a stock'}
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div className="glass-card" style={{ marginBottom: 24 }}>
          <div className="glass-card-header">
            <div className="glass-card-title">Ticker Selection</div>
          </div>
          <select
            value={selectedSymbol}
            onChange={(event) => setSelectedSymbol(event.target.value)}
            style={{
              width: '100%',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--glass-border)',
              color: 'var(--text-primary)',
              borderRadius: '0.85rem',
              padding: '0.85rem 1rem',
            }}
          >
            {symbols.map((option) => (
              <option key={option.symbol} value={option.symbol}>
                {option.symbol} · {option.name}
              </option>
            ))}
          </select>
        </div>

        {analysis ? (
          <>
            <div className="stats-grid">
              {[
                ['CMP', formatCurrency(analysis.stock.cmp), `${analysis.stock.change_percent >= 0 ? '+' : ''}${analysis.stock.change_percent.toFixed(2)}%`],
                ['Open', formatCurrency(analysis.stock.open), 'Session open'],
                ['High / Low', `${formatCurrency(analysis.stock.high)} / ${formatCurrency(analysis.stock.low)}`, 'Intraday range'],
                ['ATR', analysis.indicators.atr14.toFixed(2), 'Range volatility'],
                ['RSI', analysis.indicators.rsi14.toFixed(1), analysis.indicators.ema_alignment],
              ].map(([label, value, sub]) => (
                <div key={label} className="stat-card">
                  <div className="stat-label">{label}</div>
                  <div className="stat-value" style={{ fontSize: '1.12rem' }}>{value}</div>
                  <div className="stat-change">{sub}</div>
                </div>
              ))}
            </div>

            <div className="dashboard-grid grid-2" style={{ margin: '24px 0' }}>
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">{analysis.stock.symbol} Candles</div>
                </div>
                <CandlestickChart
                  data={candles}
                  guides={[
                    { label: 'Buy', value: recommendation?.ideal_entry ?? analysis.stock.cmp, color: '#10b981' },
                    { label: 'Stop', value: recommendation?.stop_loss ?? analysis.price_targets.stop_loss, color: '#ef4444' },
                  ]}
                />
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Pattern Reading</div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {(patterns.length ? patterns : [{
                    name: 'No dominant pattern',
                    sentiment: 'NEUTRAL' as const,
                    strength: 40,
                    explanation: 'Price structure is mixed, so pattern strength is secondary to broader momentum and volume.',
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
            </div>

            <div className="dashboard-grid grid-2">
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Candle-Supported Trade Plan</div>
                </div>
                {recommendation ? (
                  <div style={{ display: 'grid', gap: 12 }}>
                    {[
                      ['Buy zone', `${formatCurrency(recommendation.entry_low)} - ${formatCurrency(recommendation.entry_high)}`],
                      ['Sell zone', `${formatCurrency(recommendation.sell_zone_low)} - ${formatCurrency(recommendation.sell_zone_high)}`],
                      ['Hold window', `${recommendation.hold_days_min}-${recommendation.hold_days_max} sessions`],
                      ['Risk / reward', `${recommendation.risk_reward_ratio.toFixed(2)}x`],
                    ].map(([label, value]) => (
                      <div key={label} style={{ padding: '0.95rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                        <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{label}</div>
                        <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: 8 }}>{value}</div>
                      </div>
                    ))}
                    <div style={{ padding: '1rem', borderRadius: '0.9rem', background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.16)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      {recommendation.thesis}
                    </div>
                  </div>
                ) : (
                  <div style={{ color: 'var(--text-secondary)' }}>Recommendation plan unavailable.</div>
                )}
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Momentum Notes</div>
                </div>
                <ul className="detail-list">
                  {analysis.tml_details.slice(0, 5).map((detail) => (
                    <li key={detail}>{detail}</li>
                  ))}
                </ul>
              </div>
            </div>
          </>
        ) : (
          <div className="glass-card">
            <div className="loading-skeleton" style={{ height: 360, borderRadius: 16 }} />
          </div>
        )}
      </main>
    </div>
  );
}
