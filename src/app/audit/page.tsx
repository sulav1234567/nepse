'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import Sidebar from '@/components/Sidebar';
import { ApiPortfolioAudit, fetchPortfolioAudit } from '@/lib/api-client';

const SEVERITY_STYLES: Record<string, { color: string; border: string; label: string }> = {
  critical: { color: '#ff6b5e', border: 'rgba(255,67,54,0.4)', label: 'CRITICAL' },
  warning: { color: '#fbbf24', border: 'rgba(251,191,36,0.4)', label: 'WARNING' },
  info: { color: '#93c5fd', border: 'rgba(147,197,253,0.4)', label: 'INFO' },
  good: { color: '#86efac', border: 'rgba(34,197,94,0.4)', label: 'GOOD' },
};

function actionColor(action: string): string {
  if (action.includes('BUY')) return 'var(--bullish)';
  if (action.includes('SELL')) return 'var(--bearish)';
  return 'var(--text-secondary)';
}

function scoreColor(score: number): string {
  if (score >= 80) return 'var(--bullish)';
  if (score >= 60) return '#fbbf24';
  return 'var(--bearish)';
}

export default function AuditPage() {
  const [audit, setAudit] = useState<ApiPortfolioAudit | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAudit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchPortfolioAudit();
      setAudit(response);
    } catch (auditError) {
      setError(auditError instanceof Error ? auditError.message : 'Unable to run the portfolio audit.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    runAudit();
  }, [runAudit]);

  const holdings = audit?.holdings ?? [];
  const findings = audit?.findings ?? [];
  const sectors = audit?.sector_exposure ?? [];

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Self-Audit</h2>
          <div className="subtitle">Your Mero Share portfolio, audited by the AI signal engine</div>
          <div className="data-badge live">
            <span className="pulse"></span>
            {audit ? `${audit.mode.toUpperCase()} portfolio · ${new Date(audit.fetched_at).toLocaleString()}` : 'loading'}
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>{error}</div>
        ) : null}

        <div className="dashboard-grid grid-2" style={{ gridTemplateColumns: '320px 1fr', marginBottom: 24 }}>
          <div className="glass-card" style={{ textAlign: 'center' }}>
            <div className="glass-card-title" style={{ marginBottom: 12 }}>Portfolio Health</div>
            <div style={{ fontSize: '4rem', fontWeight: 800, color: scoreColor(audit?.health_score ?? 0) }}>
              {loading ? '…' : audit?.health_score ?? '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 16 }}>out of 100</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {audit?.summary ?? 'Running audit…'}
            </div>
            <button
              onClick={runAudit}
              disabled={loading}
              style={{
                marginTop: 18,
                padding: '0.6rem 1.4rem',
                borderRadius: '0.5rem',
                border: '1px solid rgba(99,102,241,0.5)',
                background: 'rgba(99,102,241,0.15)',
                color: '#a5b4fc',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              {loading ? 'Auditing…' : 'Re-run Audit'}
            </button>
          </div>

          <div>
            <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
              <div className="stat-card">
                <div className="stat-label">Holdings Value</div>
                <div className="stat-value">Rs. {audit?.totals.value?.toLocaleString() ?? '--'}</div>
                <div className="stat-change">{holdings.length} holdings</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Unrealized Gain</div>
                <div className="stat-value" style={{ color: (audit?.totals.gain ?? 0) >= 0 ? 'var(--bullish)' : 'var(--bearish)' }}>
                  {audit ? `${audit.totals.gain >= 0 ? '+' : ''}${audit.totals.gain_pct.toFixed(2)}%` : '--'}
                </div>
                <div className="stat-change">Rs. {audit?.totals.gain?.toLocaleString() ?? '--'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Idle Cash</div>
                <div className="stat-value">Rs. {audit?.totals.cash?.toLocaleString() ?? '--'}</div>
                <div className="stat-change">uninvested</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Findings</div>
                <div className="stat-value">{findings.filter((f) => f.severity === 'critical' || f.severity === 'warning').length}</div>
                <div className="stat-change">need attention</div>
              </div>
            </div>

            <div className="glass-card">
              <div className="glass-card-header">
                <div className="glass-card-title">Sector Exposure</div>
              </div>
              <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                  <BarChart data={sectors} layout="vertical">
                    <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.04)" />
                    <XAxis type="number" unit="%" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                    <YAxis type="category" dataKey="sector" width={140} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#8b95b0', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                    <Bar dataKey="weight_pct" radius={[0, 4, 4, 0]}>
                      {sectors.map((s) => (
                        <Cell key={s.sector} fill={s.weight_pct > 50 ? '#f87171' : '#6366f1'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ marginBottom: 24 }}>
          <div className="glass-card-header">
            <div className="glass-card-title">AI Findings</div>
          </div>
          {findings.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              {loading ? 'Analyzing your portfolio…' : 'No findings — connect Mero Share on the Broker Trading page to audit a live portfolio.'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {findings.map((finding, index) => {
                const style = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.info;
                return (
                  <div key={index} style={{ padding: '0.85rem 1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.75rem', border: `1px solid ${style.border}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: 800, color: style.color, letterSpacing: '0.8px' }}>{style.label}</span>
                      <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{finding.title}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{finding.detail}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Holdings — AI Verdicts</div>
          </div>
          {holdings.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No holdings found{audit ? ` in ${audit.mode} mode` : ''}. Connect Mero Share or place paper trades first.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Symbol</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Weight</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Units</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>P&L</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>AI Verdict</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Rise Prob.</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>FCS</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>AI Reasoning</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => (
                    <tr key={h.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                      <td style={{ padding: '0.6rem 0.75rem' }}>
                        <div style={{ fontWeight: 700 }}>{h.symbol}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{h.sector}</div>
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>{h.weight_pct?.toFixed(1)}%</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>{h.units}</td>
                      <td style={{ padding: '0.6rem 0.75rem', color: h.unrealized_gain_pct >= 0 ? 'var(--bullish)' : 'var(--bearish)' }}>
                        {h.unrealized_gain_pct >= 0 ? '+' : ''}{h.unrealized_gain_pct?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem', fontWeight: 700, color: actionColor(h.ai_action) }}>{h.ai_action}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>{h.rise_probability != null ? `${h.rise_probability.toFixed(1)}%` : '--'}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>{h.fcs_score != null ? h.fcs_score.toFixed(0) : '--'}</td>
                      <td style={{ padding: '0.6rem 0.75rem', fontSize: '0.75rem', color: 'var(--text-secondary)', maxWidth: 320 }}>
                        {h.ai_reasoning}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
