'use client';

import { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, LogOut, Plug, Terminal } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import {
  connectTms,
  disconnectTms,
  getTmsPortfolio,
  getTmsStatus,
  type BrokerStatus,
  type TmsHolding,
} from '@/lib/broker-client';

export default function TmsPage() {
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [holdings, setHoldings] = useState<TmsHolding[]>([]);
  const [cash, setCash] = useState<number>(0);
  const [form, setForm] = useState({ tmsUrl: '', username: '', password: '', pin: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  useEffect(() => {
    getTmsStatus()
      .then((s) => {
        setStatus(s);
        if (s.connected) loadPortfolio();
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingStatus(false));
  }, []);

  function loadPortfolio() {
    getTmsPortfolio()
      .then((p) => { setHoldings(p.holdings || []); setCash(p.cash_balance || 0); })
      .catch(() => undefined);
  }

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await connectTms(form.tmsUrl.trim(), form.username.trim(), form.password, form.pin || undefined);
      setStatus({ connected: true, provider: 'tms', tms_url: form.tmsUrl, username: form.username });
      setForm({ ...form, password: '', pin: '' });
      loadPortfolio();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect TMS.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDisconnect() {
    setBusy(true);
    try {
      await disconnectTms();
      setStatus({ connected: false, provider: 'tms' });
      setHoldings([]); setCash(0);
    } finally {
      setBusy(false);
    }
  }

  const connected = status?.connected;
  const ACCENT = '#818cf8'; // distinct from MeroShare's green — different UI by design

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '0.4rem' }}>
          <Terminal size={30} color={ACCENT} />
          <h1 style={{ fontSize: '1.9rem', fontWeight: 800 }}>TMS Trading Terminal</h1>
          {connected ? (
            <span style={chip('#00ff88')}><CheckCircle2 size={14} /> {status?.tms_url}</span>
          ) : null}
        </div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          Trade through your broker&apos;s TMS account from inside the app. Credentials are encrypted at rest.
          Live order placement is rolling out in stages — portfolio &amp; balance are available now.
        </p>

        {error ? <div style={errorBox}>{error}</div> : null}

        {loadingStatus ? (
          <div style={card}><Loader2 size={20} className="spin" /> &nbsp;Checking connection…</div>
        ) : !connected ? (
          <form onSubmit={handleConnect} style={{ ...card, maxWidth: 480, borderColor: `${ACCENT}55` }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1rem' }}>Log in to TMS</h2>
            <label style={lbl}>TMS portal URL</label>
            <input style={inp} value={form.tmsUrl} onChange={(e) => setForm({ ...form, tmsUrl: e.target.value })} placeholder="https://tms49.nepse.com.np" required />
            <label style={lbl}>Username</label>
            <input style={inp} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <div style={{ flex: 1 }}>
                <label style={lbl}>Password</label>
                <input style={inp} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
              </div>
              <div style={{ width: 120 }}>
                <label style={lbl}>PIN</label>
                <input style={inp} type="password" value={form.pin} onChange={(e) => setForm({ ...form, pin: e.target.value })} placeholder="for trading" />
              </div>
            </div>
            <button type="submit" disabled={busy} style={{ ...primaryBtn(ACCENT) }}>
              {busy ? <Loader2 size={16} className="spin" /> : <Plug size={16} />} {busy ? 'Connecting…' : 'Connect TMS'}
            </button>
          </form>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '1.25rem' }}>
            <div style={card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Portfolio · Cash Rs.{cash.toLocaleString()}</h2>
                <button onClick={handleDisconnect} disabled={busy} style={ghostBtn}><LogOut size={14} /> Disconnect</button>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ color: 'var(--text-muted)', textAlign: 'right' }}>
                    <th style={{ ...th, textAlign: 'left' }}>Symbol</th><th style={th}>Qty</th><th style={th}>LTP</th><th style={th}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => (
                    <tr key={h.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                      <td style={{ ...td, textAlign: 'left', fontWeight: 700 }}>{h.symbol}</td>
                      <td style={td}>{h.quantity.toLocaleString()}</td>
                      <td style={td}>{(h.ltp ?? 0).toLocaleString()}</td>
                      <td style={td}>{(h.value ?? (h.quantity * (h.ltp ?? 0))).toLocaleString()}</td>
                    </tr>
                  ))}
                  {holdings.length === 0 ? <tr><td colSpan={4} style={{ ...td, textAlign: 'center', color: 'var(--text-muted)' }}>No holdings.</td></tr> : null}
                </tbody>
              </table>
            </div>

            {/* Order pad — placement ships next (Phase 3: place → manage) */}
            <div style={{ ...card, borderColor: `${ACCENT}55` }}>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1rem' }}>Order Pad</h2>
              <label style={lbl}>Symbol</label>
              <input style={inp} placeholder="e.g. NABIL" disabled />
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <div style={{ flex: 1 }}><label style={lbl}>Quantity</label><input style={inp} disabled /></div>
                <div style={{ flex: 1 }}><label style={lbl}>Price</label><input style={inp} disabled /></div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                <button disabled style={{ ...primaryBtn('#4ade80'), flex: 1, opacity: 0.5 }}>BUY</button>
                <button disabled style={{ ...primaryBtn('#ef4444'), flex: 1, opacity: 0.5 }}>SELL</button>
              </div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.85rem' }}>
                Order placement is enabled in the next release. Connection, portfolio and balance are live now.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

const card: React.CSSProperties = { background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 14, padding: '1.25rem' };
const lbl: React.CSSProperties = { display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.75rem 0 0.3rem' };
const inp: React.CSSProperties = { width: '100%', padding: '0.6rem 0.8rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--glass-border)', color: 'var(--text-primary)', fontSize: '0.9rem' };
const primaryBtn = (c: string): React.CSSProperties => ({ display: 'inline-flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', marginTop: '1.1rem', padding: '0.7rem 1.3rem', borderRadius: 10, background: c, color: '#0a0e1a', fontWeight: 700, border: 'none', cursor: 'pointer' });
const ghostBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.45rem 0.85rem', borderRadius: 10, background: 'transparent', color: 'var(--text-primary)', border: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.8rem' };
const errorBox: React.CSSProperties = { ...card, color: 'var(--bearish, #ef4444)', marginBottom: '1rem', maxWidth: 480 };
const th: React.CSSProperties = { padding: '0.5rem 0.6rem', fontWeight: 600, textAlign: 'right' };
const td: React.CSSProperties = { padding: '0.55rem 0.6rem', textAlign: 'right' };
const chip = (c: string): React.CSSProperties => ({ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '0.2rem 0.6rem', borderRadius: 999, fontSize: '0.72rem', fontWeight: 700, color: c, background: `${c}1a`, border: `1px solid ${c}44` });
