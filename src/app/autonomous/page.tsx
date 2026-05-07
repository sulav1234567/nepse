'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import Sidebar from '@/components/Sidebar';
import {
  ApiAutonomousDashboardResponse,
  ApiAutonomousSignalCard,
  fetchAutonomousDashboard,
} from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';

const REFRESH_INTERVAL_MS = 120_000;

function signalColor(signal: string): string {
  switch (signal) {
    case 'STRONG BUY':
      return 'var(--strong-buy)';
    case 'BUY':
      return 'var(--buy)';
    case 'SELL':
      return 'var(--avoid)';
    case 'STRONG SELL':
      return 'var(--short-alert)';
    default:
      return 'var(--hold)';
  }
}

function metricTone(value: number, positiveThreshold: number, cautionThreshold: number): string {
  if (value >= positiveThreshold) return 'var(--bullish)';
  if (value <= cautionThreshold) return 'var(--bearish)';
  return 'var(--text-primary)';
}

function SignalMiniCard({ card }: { card: ApiAutonomousSignalCard }) {
  return (
    <div
      style={{
        padding: '1rem',
        borderRadius: '1rem',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid var(--glass-border)',
        display: 'grid',
        gap: '0.65rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: '1rem', fontWeight: 800 }}>{card.symbol}</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', lineHeight: 1.4 }}>{card.company_name}</div>
        </div>
        <div
          style={{
            padding: '0.28rem 0.55rem',
            borderRadius: '999px',
            border: `1px solid ${signalColor(card.overall_signal)}`,
            color: signalColor(card.overall_signal),
            fontSize: '0.72rem',
            fontWeight: 700,
            whiteSpace: 'nowrap',
          }}
        >
          {card.overall_signal}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
        {[
          ['Confidence', `${card.confidence_score.toFixed(0)}%`],
          ['Exp. Return', `${card.expected_return_percent.toFixed(2)}%`],
          ['Technical', `${card.technical.technical_score.toFixed(0)}`],
          ['Fundamental', `${card.fundamentals.fundamental_score.toFixed(0)}`],
        ].map(([label, value]) => (
          <div key={label} style={{ padding: '0.7rem', borderRadius: '0.8rem', background: 'rgba(0,0,0,0.12)' }}>
            <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 700, marginTop: 4 }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        {card.top_reasons.slice(0, 2).map((reason) => (
          <div key={reason} style={{ color: 'var(--text-secondary)', lineHeight: 1.55 }}>
            {reason}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {card.technical.detected_patterns.slice(0, 3).map((pattern) => (
          <span
            key={pattern}
            style={{
              padding: '0.24rem 0.48rem',
              borderRadius: '999px',
              background: 'rgba(255,255,255,0.05)',
              color: 'var(--text-secondary)',
              fontSize: '0.72rem',
            }}
          >
            {pattern}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function AutonomousPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [dashboard, setDashboard] = useState<ApiAutonomousDashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!isAuthenticated || isLoading) {
      return;
    }

    let active = true;

    async function loadDashboard() {
      try {
        const response = await fetchAutonomousDashboard();
        if (!active) return;
        setDashboard(response);
        setError(null);
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load autonomous dashboard.');
      } finally {
        if (active) setLoading(false);
      }
    }

    loadDashboard();
    const interval = window.setInterval(loadDashboard, REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Autonomous NEPSE Intelligence</h2>
          <div className="subtitle">Always-on research, scoring, regime detection, and ensemble ranking for the Nepal market.</div>
          <div className="data-badge live">
            <span className="pulse"></span>
            Refresh {REFRESH_INTERVAL_MS / 1000}s
          </div>
        </div>

        {loading ? (
          <div className="glass-card">Loading autonomous dashboard...</div>
        ) : null}

        {error ? (
          <div className="glass-card" style={{ color: 'var(--bearish)', marginBottom: 24 }}>{error}</div>
        ) : null}

        {dashboard ? (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Regime</div>
                <div className="stat-value" style={{ color: metricTone(dashboard.regime.confidence, 65, 35) }}>{dashboard.regime.regime}</div>
                <div className="stat-change">Confidence {dashboard.regime.confidence.toFixed(0)}%</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Coverage</div>
                <div className="stat-value">{dashboard.status.symbols_covered}</div>
                <div className="stat-change">{dashboard.status.bars_loaded.toLocaleString()} bars loaded</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Data Store</div>
                <div className="stat-value">{dashboard.status.database_backend.toUpperCase()}</div>
                <div className="stat-change">{dashboard.status.timescaledb_active ? 'Timescale active' : 'SQLite bootstrap mode'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Retraining</div>
                <div className="stat-value" style={{ color: dashboard.status.retrain_required ? 'var(--hold)' : 'var(--bullish)' }}>
                  {dashboard.status.retrain_required ? 'Due' : 'Healthy'}
                </div>
                <div className="stat-change">{dashboard.status.latest_training_at ? 'Model suite trained' : 'Bootstrap heuristic active'}</div>
              </div>
            </div>

            <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Regime + Monitoring</div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  <div style={{ padding: '1rem', borderRadius: '1rem', background: 'rgba(0,0,0,0.12)', lineHeight: 1.65 }}>
                    {dashboard.regime.explanation}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
                    {[
                      ['Trend', dashboard.regime.trend_score],
                      ['Volatility', dashboard.regime.volatility_score],
                      ['Breadth', dashboard.regime.breadth_score],
                      ['Liquidity', dashboard.regime.liquidity_score],
                    ].map(([label, value]) => (
                      <div key={label} style={{ padding: '0.9rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.03)' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
                        <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: 6 }}>{Number(value).toFixed(0)}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'grid', gap: 10 }}>
                    {dashboard.monitoring.map((metric) => (
                      <div key={metric.horizon} style={{ display: 'grid', gridTemplateColumns: '1fr repeat(4, minmax(0, 1fr))', gap: 10, padding: '0.85rem 0.95rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.03)' }}>
                        <div style={{ fontWeight: 700 }}>{metric.horizon}</div>
                        <div>Acc {metric.directional_accuracy.toFixed(1)}%</div>
                        <div>Sharpe {metric.sharpe_ratio.toFixed(2)}</div>
                        <div>DD {metric.max_drawdown.toFixed(1)}%</div>
                        <div>Win {metric.win_rate.toFixed(1)}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Architecture</div>
                </div>
                <div style={{ display: 'grid', gap: 10, marginBottom: 14 }}>
                  {dashboard.architecture.map((component) => (
                    <div key={component.name} style={{ padding: '0.9rem 1rem', borderRadius: '0.95rem', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                        <div style={{ fontWeight: 700 }}>{component.name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{component.layer}</div>
                      </div>
                      <div style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>{component.description}</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        {component.technologies.map((tech) => (
                          <span key={tech} style={{ padding: '0.22rem 0.45rem', borderRadius: '999px', background: 'rgba(0,0,0,0.16)', color: 'var(--text-secondary)', fontSize: '0.72rem' }}>
                            {tech}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <pre
                  style={{
                    margin: 0,
                    padding: '1rem',
                    borderRadius: '1rem',
                    background: 'rgba(8,14,24,0.7)',
                    color: '#9fd6ff',
                    overflowX: 'auto',
                    fontSize: '0.75rem',
                    lineHeight: 1.55,
                  }}
                >
                  {dashboard.architecture_diagram}
                </pre>
              </div>
            </div>

            <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Top 10 Buy</div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {dashboard.top_buys.slice(0, 5).map((card) => (
                    <SignalMiniCard key={card.symbol} card={card} />
                  ))}
                </div>
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Top 10 Avoid</div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {dashboard.top_avoids.slice(0, 5).map((card) => (
                    <SignalMiniCard key={card.symbol} card={card} />
                  ))}
                </div>
              </div>
            </div>

            <div className="dashboard-grid grid-2">
              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Sector Rotation</div>
                </div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {dashboard.sector_rotation.map((sector) => (
                    <div key={sector.sector} style={{ padding: '0.95rem 1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                        <div style={{ fontWeight: 700 }}>{sector.sector}</div>
                        <div style={{ color: metricTone(sector.rotation_score, 65, 40), fontWeight: 700 }}>{sector.signal}</div>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, marginBottom: 8 }}>
                        <div>Rotation {sector.rotation_score.toFixed(0)}</div>
                        <div>Lead {sector.leadership_score.toFixed(0)}</div>
                        <div>Value {sector.valuation_score.toFixed(0)}</div>
                        <div>Flow {sector.liquidity_score.toFixed(0)}</div>
                      </div>
                      <div style={{ color: 'var(--text-secondary)' }}>{sector.commentary}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass-card">
                <div className="glass-card-header">
                  <div className="glass-card-title">Backtest Snapshot</div>
                </div>
                {dashboard.backtest ? (
                  <div style={{ display: 'grid', gap: 12 }}>
                    <div style={{ padding: '1rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ fontWeight: 800, marginBottom: 4 }}>{dashboard.backtest.strategy_name}</div>
                      <div style={{ color: 'var(--text-secondary)' }}>
                        Annualized return {dashboard.backtest.annualized_return.toFixed(2)}% with Sharpe {dashboard.backtest.sharpe_ratio.toFixed(2)}.
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                      {[
                        ['Return', `${dashboard.backtest.annualized_return.toFixed(2)}%`],
                        ['Sharpe', dashboard.backtest.sharpe_ratio.toFixed(2)],
                        ['Max DD', `${dashboard.backtest.max_drawdown.toFixed(2)}%`],
                        ['Win Rate', `${dashboard.backtest.win_rate.toFixed(2)}%`],
                      ].map(([label, value]) => (
                        <div key={label} style={{ padding: '0.85rem', borderRadius: '0.85rem', background: 'rgba(0,0,0,0.12)' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
                          <div style={{ fontWeight: 700, marginTop: 6 }}>{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{ color: 'var(--text-secondary)' }}>Backtest history will appear after the first training cycle completes.</div>
                )}
              </div>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}
