'use client';

import Sidebar from '@/components/Sidebar';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from 'recharts';

// Demo audit data
const dailyAudit = {
  date: new Date().toISOString().split('T')[0],
  predictionsMade: 5,
  hitRate: 72,
  avgReturnOnHits: 4.8,
  avgLossOnStops: -2.1,
  sortinoRatio: 1.45,
  strongestSignal: { symbol: 'NHPC', description: 'D2 Breakout — +4.8% in 1 session on 2.1x volume' },
  weakestSignal: { symbol: 'ADBL', description: 'D5 signal failed — SIS spiked but no follow-through' },
};

const weeklyData = Array.from({ length: 10 }, (_, i) => ({
  week: `W${i + 1}`,
  hitRate: 55 + Math.random() * 30,
  avgReturn: 1.5 + Math.random() * 5,
}));

const layerPerformance = [
  { layer: 'FVL', accuracy: 68, weekChange: '+2%' },
  { layer: 'TML', accuracy: 78, weekChange: '-1%' },
  { layer: 'SSIL', accuracy: 52, weekChange: '+3%' },
  { layer: 'GTBIL', accuracy: 74, weekChange: '+1%' },
  { layer: 'MRLLL', accuracy: 61, weekChange: '0%' },
];

const monthlyHistory = Array.from({ length: 6 }, (_, i) => ({
  month: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'][i],
  dailyHitRate: 60 + Math.random() * 20,
  weeklyHitRate: 55 + Math.random() * 25,
  monthlyReturn: -5 + Math.random() * 20,
}));

export default function AuditPage() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Self-Audit Dashboard</h2>
          <div className="subtitle">Recursive evolution · Daily | Weekly | Monthly performance tracking</div>
          <div className="data-badge demo"><span className="pulse"></span>DEMO · Self-healing engine active</div>
        </div>

        {/* Daily Audit Summary */}
        <div className="glass-card" style={{ marginBottom: 24 }}>
          <div className="glass-card-header">
            <div className="glass-card-title">📊 Daily Session Audit — {dailyAudit.date}</div>
          </div>
          <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 16 }}>
            <div className="stat-card">
              <div className="stat-label">Predictions</div>
              <div className="stat-value">{dailyAudit.predictionsMade}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Hit Rate (PT1)</div>
              <div className="stat-value positive" style={{ color: dailyAudit.hitRate > 65 ? 'var(--bullish)' : 'var(--hold)' }}>{dailyAudit.hitRate}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Avg Return (Hits)</div>
              <div className="stat-value positive" style={{ color: 'var(--bullish)' }}>+{dailyAudit.avgReturnOnHits}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Avg Loss (Stops)</div>
              <div className="stat-value" style={{ color: 'var(--bearish)' }}>{dailyAudit.avgLossOnStops}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Session Sortino</div>
              <div className="stat-value" style={{ color: dailyAudit.sortinoRatio > 1.0 ? 'var(--bullish)' : 'var(--hold)' }}>{dailyAudit.sortinoRatio}</div>
            </div>
          </div>
          <div className="dashboard-grid grid-2">
            <div style={{ padding: 16, background: 'rgba(0,230,118,0.06)', borderRadius: 10, border: '1px solid rgba(0,230,118,0.15)' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--bullish)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Strongest Signal</div>
              <div style={{ marginTop: 6, fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>{dailyAudit.strongestSignal.symbol}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 2 }}>{dailyAudit.strongestSignal.description}</div>
            </div>
            <div style={{ padding: 16, background: 'rgba(255,82,82,0.06)', borderRadius: 10, border: '1px solid rgba(255,82,82,0.15)' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--bearish)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Weakest Signal</div>
              <div style={{ marginTop: 6, fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>{dailyAudit.weakestSignal.symbol}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 2 }}>{dailyAudit.weakestSignal.description}</div>
            </div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          {/* Weekly Hit Rate Chart */}
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Weekly Hit Rate Trend</div>
            </div>
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weeklyData}>
                  <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="week" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8ecf4' }} />
                  <Bar dataKey="hitRate" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Layer Performance */}
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Layer Prediction Accuracy</div>
            </div>
            <div className="layer-breakdown" style={{ marginTop: 8 }}>
              {layerPerformance.map(l => (
                <div className="layer-row" key={l.layer}>
                  <div className="layer-label">{l.layer}</div>
                  <div className="layer-bar-track">
                    <div className={`layer-bar-fill ${l.layer.toLowerCase()}`} style={{ width: `${l.accuracy}%` }} />
                  </div>
                  <div className="layer-score-number">{l.accuracy}%</div>
                  <span style={{ fontSize: '0.65rem', color: l.weekChange.startsWith('+') ? 'var(--bullish)' : l.weekChange.startsWith('-') ? 'var(--bearish)' : 'var(--text-muted)', fontWeight: 600 }}>{l.weekChange}</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(99,102,241,0.06)', borderRadius: 8, fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              <strong>Weekly Optimization:</strong> TML layer performing best (78%). SSIL accuracy low (52%) — weight reduced by 2%. GTBIL stable. Weights auto-adjusted via gradient-based optimization.
            </div>
          </div>
        </div>

        {/* Monthly Performance */}
        <div className="glass-card" style={{ marginBottom: 24 }}>
          <div className="glass-card-header">
            <div className="glass-card-title">Monthly Performance History</div>
          </div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={monthlyHistory}>
                <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="month" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 11 }} />
                <YAxis stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8ecf4' }} />
                <Line type="monotone" dataKey="dailyHitRate" name="Daily Hit %" stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1' }} />
                <Line type="monotone" dataKey="weeklyHitRate" name="Weekly Hit %" stroke="#00e676" strokeWidth={2} dot={{ fill: '#00e676' }} />
                <Line type="monotone" dataKey="monthlyReturn" name="Monthly Return %" stroke="#f59e0b" strokeWidth={2} dot={{ fill: '#f59e0b' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Current Weights & Version */}
        <div className="dashboard-grid grid-2">
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Current Layer Weights</div>
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 2 }}>
              <div>FVL: <strong style={{ color: 'var(--text-primary)' }}>25%</strong> (±0% this week)</div>
              <div>TML: <strong style={{ color: 'var(--text-primary)' }}>25%</strong> (+1% this week)</div>
              <div>SSIL: <strong style={{ color: 'var(--text-primary)' }}>15%</strong> (-2% this week)</div>
              <div>GTBIL: <strong style={{ color: 'var(--text-primary)' }}>25%</strong> (+1% this week)</div>
              <div>MRLLL: <strong style={{ color: 'var(--text-primary)' }}>10%</strong> (±0% this week)</div>
            </div>
          </div>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">System Status</div>
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 2 }}>
              <div>Version: <strong style={{ color: 'var(--accent-primary)' }}>ULTIMATE-1.0</strong></div>
              <div>State: <strong style={{ color: 'var(--bullish)' }}>ACTIVE</strong></div>
              <div>Regime: <strong style={{ color: 'var(--bullish)' }}>BULL TREND</strong> (72% confidence)</div>
              <div>Data: <strong style={{ color: 'var(--hold)' }}>DEMO MODE</strong></div>
              <div>Libraries: numpy, pandas, scipy, filterpy, sklearn, pypfopt</div>
              <div>Next Audit: End of session · Auto-evolution active</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
