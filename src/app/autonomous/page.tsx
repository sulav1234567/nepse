'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bot, ChevronDown, ChevronUp, Loader2, RefreshCw, ShieldAlert, TrendingUp } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import {
  ApiAutonomousDashboardResponse,
  ApiAutonomousSignalCard,
  ApiTraderRecommendation,
  ApiTraderStatus,
  fetchAutonomousDashboard,
  fetchTraderRecommendations,
  fetchRescoreStatus,
  fetchTraderStatus,
  refreshAutonomousSignals,
  runTraderCycle,
} from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';

const REFRESH_INTERVAL_MS = 120_000;

// ─── Plain-language helpers (make the numbers understandable) ──────────────────

const REGIME_PLAIN: Record<string, { label: string; tip: string; color: string }> = {
  BULL: { label: 'Uptrend', tip: 'Broad buying — conditions favour going long.', color: 'var(--bullish)' },
  BEAR: { label: 'Downtrend', tip: 'Broad selling — stay defensive, protect capital.', color: 'var(--bearish)' },
  SIDEWAYS: { label: 'Range-bound', tip: 'No clear trend — be selective, trade the range.', color: 'var(--hold)' },
  DISTRIBUTION: { label: 'Topping', tip: 'Smart money distributing — caution on new buys.', color: 'var(--bearish)' },
  CRISIS: { label: 'High risk', tip: 'Stress conditions — capital preservation first.', color: 'var(--short-alert)' },
};

function regimePlain(regime: string) {
  return REGIME_PLAIN[regime] ?? { label: regime || 'Unknown', tip: '', color: 'var(--text-primary)' };
}

function signalColor(signal: string): string {
  switch (signal) {
    case 'STRONG BUY': return 'var(--strong-buy)';
    case 'BUY': return 'var(--buy)';
    case 'SELL': return 'var(--avoid)';
    case 'STRONG SELL': return 'var(--short-alert)';
    default: return 'var(--hold)';
  }
}

function metricTone(value: number, positiveThreshold: number, cautionThreshold: number): string {
  if (value >= positiveThreshold) return 'var(--bullish)';
  if (value <= cautionThreshold) return 'var(--bearish)';
  return 'var(--text-primary)';
}

function relativeTime(iso?: string | null): string {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'unknown';
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  return `${Math.round(hrs / 24)} d ago`;
}

// ─── Signal card (clearer, plain-language) ─────────────────────────────────────

function SignalMiniCard({ card }: { card: ApiAutonomousSignalCard }) {
  return (
    <div style={{ padding: '1rem 1.1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--glass-border)', display: 'grid', gap: '0.6rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 800 }}>{card.symbol}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.76rem' }}>{card.company_name}</div>
        </div>
        <div style={{ padding: '0.3rem 0.7rem', borderRadius: '999px', border: `1px solid ${signalColor(card.overall_signal)}`, color: signalColor(card.overall_signal), fontSize: '0.74rem', fontWeight: 800, whiteSpace: 'nowrap' }}>
          {card.overall_signal}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {[
          ['Confidence', `${(card.confidence_score ?? 0).toFixed(0)}%`, 'How sure the model is'],
          ['Exp. return', `${(card.expected_return_percent ?? 0).toFixed(1)}%`, 'Predicted move'],
          ['Strength', `${(card.technical?.technical_score ?? 0).toFixed(0)}/100`, 'Technical setup'],
        ].map(([label, value, tip]) => (
          <div key={label} title={tip} style={{ padding: '0.55rem 0.6rem', borderRadius: '0.6rem', background: 'rgba(0,0,0,0.14)' }}>
            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, marginTop: 3 }}>{value}</div>
          </div>
        ))}
      </div>

      {(card.top_reasons ?? []).slice(0, 2).map((reason) => (
        <div key={reason} style={{ color: 'var(--text-secondary)', lineHeight: 1.5, fontSize: '0.82rem' }}>• {reason}</div>
      ))}
    </div>
  );
}

// ─── Trading agent panel ───────────────────────────────────────────────────────

function TradingAgentPanel() {
  const [status, setStatus] = useState<ApiTraderStatus | null>(null);
  const [recommendations, setRecommendations] = useState<ApiTraderRecommendation[]>([]);
  const [recsLoading, setRecsLoading] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await fetchTraderStatus());
      setAgentError(null);
    } catch (e) {
      setAgentError(e instanceof Error ? e.message : 'Unable to load agent status.');
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = window.setInterval(loadStatus, 30_000);
    return () => window.clearInterval(interval);
  }, [loadStatus]);

  const handleLoadRecommendations = async () => {
    setRecsLoading(true);
    setAgentError(null);
    try {
      setRecommendations(await fetchTraderRecommendations(10));
    } catch (e) {
      setAgentError(e instanceof Error ? e.message : 'Unable to load recommendations.');
    } finally {
      setRecsLoading(false);
    }
  };

  const handleRunCycle = async () => {
    setRunMessage(null);
    setAgentError(null);
    try {
      const r = await runTraderCycle();
      setRunMessage(`${r.message} (${r.mode} mode)`);
      window.setTimeout(loadStatus, 4000);
    } catch (e) {
      setAgentError(e instanceof Error ? e.message : 'Unable to start agent cycle.');
    }
  };

  return (
    <div className="glass-card" style={{ marginBottom: 24 }}>
      <div className="glass-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div className="glass-card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bot size={18} /> Autonomous Trading Agent
          {status ? (
            <span style={{ marginLeft: 4, padding: '0.2rem 0.55rem', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700, border: `1px solid ${status.mode === 'paper' ? 'var(--bullish)' : 'var(--bearish)'}`, color: status.mode === 'paper' ? 'var(--bullish)' : 'var(--bearish)', textTransform: 'uppercase' }}>
              {status.mode} mode
            </span>
          ) : null}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button type="button" onClick={handleLoadRecommendations} disabled={recsLoading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.5rem 0.9rem', borderRadius: '0.7rem', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)', cursor: 'pointer' }}>
            {recsLoading ? <Loader2 size={14} className="spin" /> : <TrendingUp size={14} />}
            {recsLoading ? 'Scanning…' : 'Get Recommendations'}
          </button>
          <button type="button" onClick={handleRunCycle} disabled={status?.is_running ?? false}
            style={{ padding: '0.5rem 0.9rem', borderRadius: '0.7rem', border: '1px solid var(--bullish)', background: 'rgba(0,200,120,0.12)', color: 'var(--bullish)', cursor: 'pointer', fontWeight: 700 }}>
            {status?.is_running ? 'Agent Running…' : 'Run Agent Cycle'}
          </button>
        </div>
      </div>

      {agentError ? <div style={{ color: 'var(--bearish)', marginBottom: 12 }}>{agentError}</div> : null}
      {runMessage ? <div style={{ color: 'var(--bullish)', marginBottom: 12 }}>{runMessage}</div> : null}

      {status ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
          {[
            ['Open Positions', String(status.open_positions.length)],
            ['Total Trades', String(status.total_trades)],
            ['Realized P&L', `Rs ${status.total_realized_pnl.toLocaleString()}`],
            ['Portfolio Value', `Rs ${status.portfolio_value.toLocaleString()}`],
            ['Cash', `Rs ${status.cash_balance.toLocaleString()}`],
            ['Win Rate', `${status.win_rate.toFixed(1)}%`],
          ].map(([label, value]) => (
            <div key={label} style={{ padding: '0.85rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: 5 }}>{value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', marginBottom: 12 }}>
          <Loader2 size={16} className="spin" /> Loading agent status…
        </div>
      )}

      {status && status.open_positions.length > 0 ? (
        <div style={{ marginBottom: 16, overflowX: 'auto' }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Open Positions</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                {['Symbol', 'Units', 'Entry', 'Current', 'Stop', 'Target', 'P&L %'].map((h) => <th key={h} style={{ padding: '0.4rem 0.6rem' }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {status.open_positions.map((p) => (
                <tr key={p.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                  <td style={{ padding: '0.45rem 0.6rem', fontWeight: 700 }}>{p.symbol}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{p.units}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{p.entry_price.toFixed(2)}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{p.current_price.toFixed(2)}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{p.stop_loss.toFixed(2)}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{p.target_1.toFixed(2)}</td>
                  <td style={{ padding: '0.45rem 0.6rem', color: p.unrealized_pnl_pct >= 0 ? 'var(--bullish)' : 'var(--bearish)', fontWeight: 700 }}>{p.unrealized_pnl_pct.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {recommendations.length > 0 ? (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Top Buy Recommendations (model + 5-layer ranked)</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                {['#', 'Symbol', 'Sector', 'CMP', 'Rise Prob', 'R:R', 'Stop', 'Target', 'Size %', 'Why'].map((h) => <th key={h} style={{ padding: '0.4rem 0.6rem' }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {recommendations.map((rec) => (
                <tr key={rec.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{rec.rank}</td>
                  <td style={{ padding: '0.45rem 0.6rem', fontWeight: 700 }}>{rec.symbol}</td>
                  <td style={{ padding: '0.45rem 0.6rem', color: 'var(--text-secondary)' }}>{rec.sector}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{rec.cmp.toFixed(1)}</td>
                  <td style={{ padding: '0.45rem 0.6rem', color: rec.rise_probability >= 68 ? 'var(--bullish)' : 'var(--text-primary)', fontWeight: 700 }}>{rec.rise_probability.toFixed(1)}%</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{rec.risk_reward.toFixed(2)}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{rec.stop_loss.toFixed(1)}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{rec.target_1.toFixed(1)}</td>
                  <td style={{ padding: '0.45rem 0.6rem' }}>{rec.kelly_size_pct.toFixed(1)}%</td>
                  <td style={{ padding: '0.45rem 0.6rem', color: 'var(--text-secondary)', maxWidth: 320 }}>{rec.reasoning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

// ─── Loading skeleton ──────────────────────────────────────────────────────────

function DashboardSkeleton({ message }: { message: string }) {
  return (
    <div style={{ display: 'grid', gap: 20 }}>
      <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--text-secondary)' }}>
        <Loader2 size={20} className="spin" color="var(--accent)" /> {message}
      </div>
      <div className="stats-grid">
        {[0, 1, 2, 3].map((i) => <div key={i} className="loading-skeleton" style={{ height: 96, borderRadius: 12 }} />)}
      </div>
      <div className="loading-skeleton" style={{ height: 180, borderRadius: 12 }} />
      <div className="dashboard-grid grid-2">
        <div className="loading-skeleton" style={{ height: 320, borderRadius: 12 }} />
        <div className="loading-skeleton" style={{ height: 320, borderRadius: 12 }} />
      </div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function AutonomousPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [dashboard, setDashboard] = useState<ApiAutonomousDashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rescoring, setRescoring] = useState(false);
  const [autoRescored, setAutoRescored] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const scoringIsStale =
    !!dashboard?.status.latest_training_at &&
    (!dashboard?.status.latest_scoring_at ||
      new Date(dashboard.status.latest_training_at).getTime() > new Date(dashboard.status.latest_scoring_at).getTime());
  const hasRatedBuys = dashboard?.top_buys.some((c) => c.overall_signal === 'BUY' || c.overall_signal === 'STRONG BUY') ?? false;

  const loadDashboard = useCallback(async () => {
    try {
      const response = await fetchAutonomousDashboard();
      setDashboard(response);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load autonomous dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Re-score with the latest trained model. Non-blocking: kick off the background
  // rescore, poll until it finishes (it scores all ~334 stocks), then reload.
  const handleRescore = useCallback(async () => {
    setRescoring(true);
    setError(null);
    try {
      await refreshAutonomousSignals(25);
      const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
      for (let i = 0; i < 60; i += 1) {
        await sleep(4000);
        try {
          const st = await fetchRescoreStatus();
          if (!st.in_progress) break;
        } catch {
          /* keep polling */
        }
      }
      await loadDashboard();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Rescore failed — the model may still be loading.');
    } finally {
      setRescoring(false);
    }
  }, [loadDashboard]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/auth/login');
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!isAuthenticated || isLoading) return;
    loadDashboard();
    const interval = window.setInterval(loadDashboard, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [isAuthenticated, isLoading, loadDashboard]);

  // Auto-rescore ONCE when we detect the signals are older than the model.
  useEffect(() => {
    if (scoringIsStale && !autoRescored && !rescoring) {
      setAutoRescored(true);
      handleRescore();
    }
  }, [scoringIsStale, autoRescored, rescoring, handleRescore]);

  if (isLoading || !isAuthenticated) return null;

  const regime = regimePlain(dashboard?.regime.regime ?? '');
  const topPick = dashboard?.top_buys?.[0];

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Autonomous NEPSE Intelligence</h2>
          <div className="subtitle">The trained model scores every stock, ranks buys &amp; avoids, reads the market regime, and (optionally) trades for you.</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
            <div className="data-badge live"><span className="pulse" /> Auto-refresh {REFRESH_INTERVAL_MS / 1000}s</div>
            {dashboard ? <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Signals scored {relativeTime(dashboard.status.latest_scoring_at)} · model trained {relativeTime(dashboard.status.latest_training_at)}</span> : null}
            <button type="button" onClick={handleRescore} disabled={rescoring}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem', borderRadius: '0.6rem', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.8rem' }}>
              <RefreshCw size={13} className={rescoring ? 'spin' : undefined} /> {rescoring ? 'Rescoring…' : 'Rescore now'}
            </button>
          </div>
        </div>

        {error ? <div className="glass-card" style={{ color: 'var(--bearish)', marginBottom: 20 }}>{error}</div> : null}

        {/* Stale → actionable, with live rescore feedback */}
        {rescoring ? (
          <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, color: 'var(--accent)' }}>
            <Loader2 size={18} className="spin" /> Rescoring every stock with the latest trained model… this takes a few seconds.
          </div>
        ) : scoringIsStale ? (
          <div className="glass-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 20, borderColor: 'var(--hold)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--hold)' }}>
              <ShieldAlert size={18} /> A newer model is trained — the picks below are from the previous run.
            </div>
            <button type="button" onClick={handleRescore} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.45rem 0.9rem', borderRadius: '0.6rem', border: '1px solid var(--accent)', background: 'rgba(0,255,136,0.1)', color: 'var(--accent)', cursor: 'pointer', fontWeight: 700 }}>
              <RefreshCw size={14} /> Rescore with new model
            </button>
          </div>
        ) : null}

        {loading && !dashboard ? (
          <DashboardSkeleton message="Loading autonomous intelligence — fetching live data and model scores…" />
        ) : dashboard ? (
          <>
            {/* Understandable summary */}
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Market Regime</div>
                <div className="stat-value" style={{ color: regime.color }}>{regime.label}</div>
                <div className="stat-change" title={regime.tip}>{regime.tip || `Confidence ${(dashboard.regime.confidence ?? 0).toFixed(0)}%`}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Top AI Pick</div>
                <div className="stat-value" style={{ color: topPick ? signalColor(topPick.overall_signal) : 'var(--text-muted)' }}>{topPick?.symbol ?? '—'}</div>
                <div className="stat-change">{topPick ? `${topPick.overall_signal} · ${(topPick.confidence_score ?? 0).toFixed(0)}% conf` : 'No buy signal yet'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Stocks Analyzed</div>
                <div className="stat-value">{dashboard.status.symbols_covered}</div>
                <div className="stat-change">{(dashboard.status.bars_loaded ?? 0).toLocaleString()} price bars</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Model Status</div>
                <div className="stat-value" style={{ color: dashboard.status.latest_training_at ? 'var(--bullish)' : 'var(--hold)' }}>
                  {dashboard.status.latest_training_at ? 'Trained' : 'Bootstrap'}
                </div>
                <div className="stat-change">{dashboard.status.retrain_required ? 'Retrain recommended' : `Updated ${relativeTime(dashboard.status.latest_training_at)}`}</div>
              </div>
            </div>

            <TradingAgentPanel />

            {/* Top buys / avoids — the core, plain-language */}
            <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
              <div className="glass-card">
                <div className="glass-card-header"><div className="glass-card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><TrendingUp size={18} color="var(--bullish)" /> Top Buy Candidates</div></div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {!hasRatedBuys ? (
                    <div style={{ color: 'var(--text-secondary)', lineHeight: 1.6, fontSize: '0.85rem' }}>
                      No stock cleared the buy threshold in the latest scoring run — showing the highest-ranked candidates from the model.
                    </div>
                  ) : null}
                  {(dashboard.top_buys ?? []).slice(0, 10).map((card) => <SignalMiniCard key={card.symbol} card={card} />)}
                </div>
              </div>
              <div className="glass-card">
                <div className="glass-card-header"><div className="glass-card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><ShieldAlert size={18} color="var(--bearish)" /> Stocks to Avoid</div></div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {(dashboard.top_avoids ?? []).slice(0, 10).map((card) => <SignalMiniCard key={card.symbol} card={card} />)}
                </div>
              </div>
            </div>

            {/* Regime detail + sector rotation */}
            <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
              <div className="glass-card">
                <div className="glass-card-header"><div className="glass-card-title">Why this regime?</div></div>
                <div style={{ padding: '1rem', borderRadius: '0.9rem', background: 'rgba(0,0,0,0.12)', lineHeight: 1.6, marginBottom: 12 }}>{dashboard.regime.explanation}</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                  {[
                    ['Trend', dashboard.regime.trend_score, 'Direction strength'],
                    ['Volatility', dashboard.regime.volatility_score, 'Price swings'],
                    ['Breadth', dashboard.regime.breadth_score, 'How many stocks participate'],
                    ['Liquidity', dashboard.regime.liquidity_score, 'Money flowing in'],
                  ].map(([label, value, tip]) => (
                    <div key={label as string} title={tip as string} style={{ padding: '0.85rem', borderRadius: '0.8rem', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</div>
                      <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: 6 }}>{Number(value ?? 0).toFixed(0)}<span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/100</span></div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass-card">
                <div className="glass-card-header"><div className="glass-card-title">Sector Rotation</div></div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {(dashboard.sector_rotation ?? []).map((sector) => (
                    <div key={sector.sector} style={{ padding: '0.85rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                        <div style={{ fontWeight: 700 }}>{sector.sector}</div>
                        <div style={{ color: metricTone(sector.rotation_score, 65, 40), fontWeight: 700 }}>{sector.signal}</div>
                      </div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: 4 }}>{sector.commentary}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Backtest */}
            {dashboard.backtest ? (
              <div className="glass-card" style={{ marginBottom: 24 }}>
                <div className="glass-card-header"><div className="glass-card-title">Strategy Backtest</div></div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
                  {[
                    ['Annual Return', `${dashboard.backtest.annualized_return.toFixed(1)}%`, dashboard.backtest.annualized_return >= 0 ? 'var(--bullish)' : 'var(--bearish)'],
                    ['Sharpe', dashboard.backtest.sharpe_ratio.toFixed(2), 'var(--text-primary)'],
                    ['Max Drawdown', `${dashboard.backtest.max_drawdown.toFixed(1)}%`, 'var(--bearish)'],
                    ['Win Rate', `${dashboard.backtest.win_rate.toFixed(1)}%`, 'var(--text-primary)'],
                  ].map(([label, value, color]) => (
                    <div key={label} style={{ padding: '0.9rem', borderRadius: '0.85rem', background: 'rgba(0,0,0,0.12)' }}>
                      <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: 5, color }}>{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Developer internals — collapsed by default (was cluttering the page) */}
            <button type="button" onClick={() => setShowDetails((s) => !s)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.5rem 0.9rem', borderRadius: '0.6rem', border: '1px solid var(--glass-border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: 16 }}>
              {showDetails ? <ChevronUp size={15} /> : <ChevronDown size={15} />} System details &amp; model monitoring
            </button>

            {showDetails ? (
              <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
                <div className="glass-card">
                  <div className="glass-card-header"><div className="glass-card-title">Model Monitoring</div></div>
                  <div style={{ display: 'grid', gap: 10 }}>
                    {(dashboard.monitoring ?? []).map((m) => (
                      <div key={m.horizon} style={{ display: 'grid', gridTemplateColumns: '1fr repeat(4, 1fr)', gap: 10, padding: '0.8rem 0.9rem', borderRadius: '0.8rem', background: 'rgba(255,255,255,0.03)' }}>
                        <div style={{ fontWeight: 700 }}>{m.horizon}</div>
                        <div>Acc {m.directional_accuracy.toFixed(1)}%</div>
                        <div>Sharpe {m.sharpe_ratio.toFixed(2)}</div>
                        <div>DD {m.max_drawdown.toFixed(1)}%</div>
                        <div>Win {m.win_rate.toFixed(1)}%</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 12, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Data store: {dashboard.status.database_backend?.toUpperCase()} · {dashboard.status.timescaledb_active ? 'Timescale active' : 'SQLite mode'} · {(dashboard.status.macro_points_loaded ?? 0).toLocaleString()} macro points · {(dashboard.status.news_articles_loaded ?? 0).toLocaleString()} news
                  </div>
                </div>
                <div className="glass-card">
                  <div className="glass-card-header"><div className="glass-card-title">Architecture</div></div>
                  <div style={{ display: 'grid', gap: 10 }}>
                    {(dashboard.architecture ?? []).map((c) => (
                      <div key={c.name} style={{ padding: '0.85rem 1rem', borderRadius: '0.9rem', background: 'rgba(255,255,255,0.03)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 4 }}>
                          <div style={{ fontWeight: 700 }}>{c.name}</div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{c.layer}</div>
                        </div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>{c.description}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </main>
    </div>
  );
}
