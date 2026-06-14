'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Building2, CheckCircle2, Loader2, LogOut, ShieldCheck, Wallet } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import {
  connectMeroShare,
  disconnectMeroShare,
  getMeroSharePortfolio,
  getMeroShareStatus,
  type BrokerStatus,
  type MeroSharePortfolio,
} from '@/lib/broker-client';

export default function MeroSharePage() {
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [portfolio, setPortfolio] = useState<MeroSharePortfolio | null>(null);
  const [dp, setDp] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  useEffect(() => {
    getMeroShareStatus()
      .then((s) => {
        setStatus(s);
        if (s.connected) {
          getMeroSharePortfolio().then(setPortfolio).catch(() => undefined);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingStatus(false));
  }, []);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await connectMeroShare(dp.trim(), username.trim(), password);
      setPortfolio(res.portfolio);
      setStatus({ connected: true, provider: 'meroshare', dp, username });
      setPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect MeroShare.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDisconnect() {
    setBusy(true);
    try {
      await disconnectMeroShare();
      setStatus({ connected: false, provider: 'meroshare' });
      setPortfolio(null);
    } finally {
      setBusy(false);
    }
  }

  const connected = status?.connected;

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '0.4rem' }}>
          <Building2 size={30} color="var(--accent)" />
          <h1 style={{ fontSize: '1.9rem', fontWeight: 800 }}>MeroShare</h1>
          {connected ? (
            <span style={chip('#00ff88')}><CheckCircle2 size={14} /> Connected</span>
          ) : null}
        </div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          Link your CDSC MeroShare account to pull your real holdings for the AI portfolio self-audit.
          Your password is encrypted at rest — never stored in plaintext.
        </p>

        {error ? <div style={errorBox}>{error}</div> : null}

        {loadingStatus ? (
          <div style={card}><Loader2 size={20} className="spin" /> &nbsp;Checking connection…</div>
        ) : !connected ? (
          <form onSubmit={handleConnect} style={{ ...card, maxWidth: 460 }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1rem' }}>Connect your account</h2>
            <label style={label}>Depository Participant (DP)</label>
            <input style={input} value={dp} onChange={(e) => setDp(e.target.value)} placeholder="e.g. 13700" required />
            <label style={label}>Username / Client ID</label>
            <input style={input} value={username} onChange={(e) => setUsername(e.target.value)} required />
            <label style={label}>Password</label>
            <input style={input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button type="submit" disabled={busy} style={primaryBtn}>
              {busy ? <Loader2 size={16} className="spin" /> : <ShieldCheck size={16} />}
              {busy ? 'Connecting…' : 'Connect securely'}
            </button>
          </form>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <Stat label="PORTFOLIO VALUE" value={`Rs.${(portfolio?.total_value ?? 0).toLocaleString()}`} color="#00ff88" icon={<Wallet size={18} />} />
              <Stat label="TOTAL COST" value={`Rs.${(portfolio?.total_cost ?? 0).toLocaleString()}`} color="#818cf8" />
              <Stat label="UNREALIZED P&L" value={`Rs.${(portfolio?.total_gain ?? 0).toLocaleString()}`} color={(portfolio?.total_gain ?? 0) >= 0 ? '#4ade80' : '#ef4444'} sub={`${(portfolio?.total_gain_pct ?? 0).toFixed(2)}%`} />
              <Stat label="HOLDINGS" value={`${portfolio?.holdings.length ?? 0}`} color="#facc15" />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <Link href="/audit" style={primaryBtnLink}><ShieldCheck size={16} /> Run AI self-audit</Link>
              <button onClick={handleDisconnect} disabled={busy} style={ghostBtn}><LogOut size={16} /> Disconnect</button>
            </div>

            <div style={card}>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1rem' }}>Holdings</h2>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ color: 'var(--text-muted)', textAlign: 'right' }}>
                      <th style={{ ...th, textAlign: 'left' }}>Symbol</th>
                      <th style={th}>Units</th><th style={th}>LTP</th><th style={th}>WACC</th>
                      <th style={th}>Value</th><th style={th}>P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(portfolio?.holdings ?? []).map((h) => (
                      <tr key={h.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                        <td style={{ ...td, textAlign: 'left', fontWeight: 700 }}>{h.symbol}</td>
                        <td style={td}>{h.units.toLocaleString()}</td>
                        <td style={td}>{h.ltp.toLocaleString()}</td>
                        <td style={td}>{h.wacc.toLocaleString()}</td>
                        <td style={td}>{(h.units * h.ltp).toLocaleString()}</td>
                        <td style={{ ...td, color: h.unrealized_gain >= 0 ? '#4ade80' : '#ef4444' }}>
                          {h.unrealized_gain >= 0 ? '+' : ''}{h.unrealized_gain.toLocaleString()} ({h.unrealized_gain_pct.toFixed(1)}%)
                        </td>
                      </tr>
                    ))}
                    {(portfolio?.holdings.length ?? 0) === 0 ? (
                      <tr><td colSpan={6} style={{ ...td, textAlign: 'center', color: 'var(--text-muted)' }}>No holdings found.</td></tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, color, sub, icon }: { label: string; value: string; color: string; sub?: string; icon?: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.65rem', letterSpacing: '0.08em' }}>
        {label} {icon}
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: 800, color, fontFamily: 'var(--font-mono)', marginTop: 6 }}>{value}</div>
      {sub ? <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{sub}</div> : null}
    </div>
  );
}

const card: React.CSSProperties = { background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 14, padding: '1.25rem' };
const label: React.CSSProperties = { display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.75rem 0 0.3rem' };
const input: React.CSSProperties = { width: '100%', padding: '0.65rem 0.85rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--glass-border)', color: 'var(--text-primary)', fontSize: '0.9rem' };
const primaryBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '0.5rem', marginTop: '1.25rem', padding: '0.7rem 1.3rem', borderRadius: 10, background: 'var(--accent)', color: '#04210f', fontWeight: 700, border: 'none', cursor: 'pointer' };
const primaryBtnLink: React.CSSProperties = { ...primaryBtn, marginTop: 0, textDecoration: 'none' };
const ghostBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.7rem 1.3rem', borderRadius: 10, background: 'transparent', color: 'var(--text-primary)', border: '1px solid var(--glass-border)', cursor: 'pointer' };
const errorBox: React.CSSProperties = { ...card, color: 'var(--bearish, #ef4444)', marginBottom: '1rem', maxWidth: 460 };
const th: React.CSSProperties = { padding: '0.5rem 0.6rem', fontWeight: 600, textAlign: 'right' };
const td: React.CSSProperties = { padding: '0.55rem 0.6rem', textAlign: 'right' };
const chip = (c: string): React.CSSProperties => ({ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '0.2rem 0.6rem', borderRadius: 999, fontSize: '0.72rem', fontWeight: 700, color: c, background: `${c}1a`, border: `1px solid ${c}44` });
