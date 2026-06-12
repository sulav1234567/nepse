'use client';

import { useCallback, useEffect, useState } from 'react';

import Sidebar from '@/components/Sidebar';
import {
  ApiBrokerPortfolio,
  ApiTradeRecord,
  ApiTraderPosition,
  ApiTraderStatus,
  connectBroker,
  fetchTraderPortfolio,
  fetchTraderPositions,
  fetchTraderStatus,
  fetchTraderTrades,
  forceExitPosition,
  placeManualTrade,
  runTraderCycle,
} from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 30_000;

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.6rem 0.8rem',
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid var(--glass-border)',
  borderRadius: '0.5rem',
  color: 'var(--text-primary)',
  fontSize: '0.85rem',
};

const labelStyle: React.CSSProperties = {
  fontSize: '0.7rem',
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  marginBottom: 4,
  display: 'block',
};

const buttonStyle: React.CSSProperties = {
  padding: '0.65rem 1.4rem',
  borderRadius: '0.5rem',
  border: '1px solid rgba(99,102,241,0.5)',
  background: 'rgba(99,102,241,0.15)',
  color: '#a5b4fc',
  fontWeight: 600,
  fontSize: '0.85rem',
  cursor: 'pointer',
};

function gainColor(value: number): string {
  return value >= 0 ? 'var(--bullish)' : 'var(--bearish)';
}

export default function TraderPage() {
  const [status, setStatus] = useState<ApiTraderStatus | null>(null);
  const [portfolio, setPortfolio] = useState<ApiBrokerPortfolio | null>(null);
  const [positions, setPositions] = useState<ApiTraderPosition[]>([]);
  const [trades, setTrades] = useState<ApiTradeRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Broker connect form
  const [paperMode, setPaperMode] = useState(true);
  const [msClientId, setMsClientId] = useState('');
  const [msPassword, setMsPassword] = useState('');
  const [tmsUrl, setTmsUrl] = useState('');
  const [tmsUsername, setTmsUsername] = useState('');
  const [tmsPassword, setTmsPassword] = useState('');
  const [tmsPin, setTmsPin] = useState('');
  const [connecting, setConnecting] = useState(false);

  // Manual trade form
  const [tradeSymbol, setTradeSymbol] = useState('');
  const [tradeAction, setTradeAction] = useState<'BUY' | 'SELL'>('BUY');
  const [tradeQty, setTradeQty] = useState('10');
  const [tradePrice, setTradePrice] = useState('');
  const [placing, setPlacing] = useState(false);
  const [runningCycle, setRunningCycle] = useState(false);

  const loadAll = useCallback(async () => {
    const results = await Promise.allSettled([
      fetchTraderStatus(),
      fetchTraderPortfolio(),
      fetchTraderPositions(),
      fetchTraderTrades(),
    ]);
    if (results[0].status === 'fulfilled') setStatus(results[0].value);
    if (results[1].status === 'fulfilled') setPortfolio(results[1].value);
    if (results[2].status === 'fulfilled') setPositions(results[2].value);
    if (results[3].status === 'fulfilled') setTrades(results[3].value);
    if (results.every((r) => r.status === 'rejected')) {
      setError('Unable to reach the trading backend.');
    } else {
      setError(null);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const interval = window.setInterval(loadAll, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [loadAll]);

  async function handleConnect() {
    setConnecting(true);
    setNotice(null);
    try {
      const response = await connectBroker({
        paper_mode: paperMode,
        mero_share_client_id: msClientId || undefined,
        mero_share_password: msPassword || undefined,
        tms_url: tmsUrl || undefined,
        tms_username: tmsUsername || undefined,
        tms_password: tmsPassword || undefined,
        tms_pin: tmsPin || undefined,
      });
      setNotice(response.message);
      setMsPassword('');
      setTmsPassword('');
      setTmsPin('');
      await loadAll();
    } catch (connectError) {
      setNotice(connectError instanceof Error ? connectError.message : 'Connection failed.');
    } finally {
      setConnecting(false);
    }
  }

  async function handleManualTrade() {
    const quantity = Number.parseInt(tradeQty, 10);
    const price = Number.parseFloat(tradePrice);
    if (!tradeSymbol || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(price) || price <= 0) {
      setNotice('Enter a valid symbol, quantity, and price.');
      return;
    }
    setPlacing(true);
    setNotice(null);
    try {
      const record = await placeManualTrade({
        symbol: tradeSymbol.toUpperCase(),
        action: tradeAction,
        quantity,
        price,
        notes: 'Manual trade via Trader UI',
      });
      setNotice(`${record.action} ${record.symbol} x${record.quantity} — ${record.status}${record.notes ? ` (${record.notes})` : ''}`);
      setTradeSymbol('');
      setTradePrice('');
      await loadAll();
    } catch (tradeError) {
      setNotice(tradeError instanceof Error ? tradeError.message : 'Trade failed.');
    } finally {
      setPlacing(false);
    }
  }

  async function handleExit(symbol: string) {
    try {
      const response = await forceExitPosition(symbol);
      setNotice(response.message);
      await loadAll();
    } catch (exitError) {
      setNotice(exitError instanceof Error ? exitError.message : 'Exit failed.');
    }
  }

  async function handleRunCycle() {
    setRunningCycle(true);
    setNotice(null);
    try {
      const response = await runTraderCycle();
      setNotice(`${response.message} (${response.mode} mode)`);
    } catch (runError) {
      setNotice(runError instanceof Error ? runError.message : 'Could not start the agent cycle.');
    } finally {
      setRunningCycle(false);
    }
  }

  const holdings = portfolio?.holdings ?? [];
  const liveMode = status?.mode === 'live';

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Broker Trading</h2>
          <div className="subtitle">Mero Share portfolio + TMS order execution for the autonomous agent</div>
          <div className="data-badge live">
            <span className="pulse"></span>
            {status ? `${status.mode.toUpperCase()} MODE` : 'CONNECTING'} · refresh {REFRESH_INTERVAL_MS / 1000}s
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>{error}</div>
        ) : null}
        {notice ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--text-secondary)' }}>{notice}</div>
        ) : null}

        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 24 }}>
          <div className="stat-card">
            <div className="stat-label">Mode</div>
            <div className="stat-value" style={{ color: liveMode ? 'var(--bearish)' : 'var(--bullish)' }}>
              {status?.mode?.toUpperCase() ?? '--'}
            </div>
            <div className="stat-change">{liveMode ? 'real orders' : 'simulated orders'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Cash Balance</div>
            <div className="stat-value">Rs. {status?.cash_balance?.toLocaleString() ?? '--'}</div>
            <div className="stat-change">available to trade</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Portfolio Value</div>
            <div className="stat-value">Rs. {portfolio?.total_value?.toLocaleString() ?? '--'}</div>
            <div className="stat-change" style={{ color: gainColor(portfolio?.total_gain ?? 0) }}>
              {portfolio ? `${portfolio.total_gain >= 0 ? '+' : ''}${portfolio.total_gain_pct.toFixed(2)}%` : '--'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Trades</div>
            <div className="stat-value">{status?.total_trades ?? '--'}</div>
            <div className="stat-change">win rate {status?.win_rate?.toFixed(0) ?? '--'}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Realized P&L</div>
            <div className="stat-value" style={{ color: gainColor(status?.total_realized_pnl ?? 0) }}>
              Rs. {status?.total_realized_pnl?.toLocaleString() ?? '--'}
            </div>
            <div className="stat-change">max drawdown {status?.max_drawdown_pct?.toFixed(1) ?? '--'}%</div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Broker Connection</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.85rem' }}>
                <input type="checkbox" checked={paperMode} onChange={(e) => setPaperMode(e.target.checked)} />
                Paper trading mode (safe — no real orders)
              </label>
            </div>
            {!paperMode ? (
              <div style={{ padding: '0.7rem 1rem', marginBottom: 16, background: 'rgba(255,67,54,0.08)', border: '1px solid rgba(255,67,54,0.3)', borderRadius: '0.5rem', color: '#ff6b5e', fontSize: '0.8rem' }}>
                Live mode places real orders with real money through your TMS account.
              </div>
            ) : null}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={labelStyle}>Mero Share Client ID</label>
                <input style={inputStyle} value={msClientId} onChange={(e) => setMsClientId(e.target.value)} placeholder="e.g. 130" autoComplete="off" />
              </div>
              <div>
                <label style={labelStyle}>Mero Share Password</label>
                <input style={inputStyle} type="password" value={msPassword} onChange={(e) => setMsPassword(e.target.value)} autoComplete="new-password" />
              </div>
              <div>
                <label style={labelStyle}>TMS URL</label>
                <input style={inputStyle} value={tmsUrl} onChange={(e) => setTmsUrl(e.target.value)} placeholder="https://tms49.nepsetms.com.np" autoComplete="off" />
              </div>
              <div>
                <label style={labelStyle}>TMS Username</label>
                <input style={inputStyle} value={tmsUsername} onChange={(e) => setTmsUsername(e.target.value)} autoComplete="off" />
              </div>
              <div>
                <label style={labelStyle}>TMS Password</label>
                <input style={inputStyle} type="password" value={tmsPassword} onChange={(e) => setTmsPassword(e.target.value)} autoComplete="new-password" />
              </div>
              <div>
                <label style={labelStyle}>TMS PIN</label>
                <input style={inputStyle} type="password" value={tmsPin} onChange={(e) => setTmsPin(e.target.value)} autoComplete="new-password" />
              </div>
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button style={buttonStyle} onClick={handleConnect} disabled={connecting}>
                {connecting ? 'Connecting…' : 'Connect Broker'}
              </button>
              <button
                style={{ ...buttonStyle, borderColor: 'rgba(34,197,94,0.5)', background: 'rgba(34,197,94,0.12)', color: '#86efac' }}
                onClick={handleRunCycle}
                disabled={runningCycle || Boolean(status?.is_running)}
              >
                {status?.is_running ? 'Agent Running…' : runningCycle ? 'Starting…' : 'Run Agent Cycle'}
              </button>
            </div>
            <div style={{ marginTop: 12, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Credentials are sent to your own backend only and are not stored in the browser.
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Manual Trade</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={labelStyle}>Symbol</label>
                <input style={inputStyle} value={tradeSymbol} onChange={(e) => setTradeSymbol(e.target.value.toUpperCase())} placeholder="NABIL" />
              </div>
              <div>
                <label style={labelStyle}>Action</label>
                <select style={inputStyle} value={tradeAction} onChange={(e) => setTradeAction(e.target.value as 'BUY' | 'SELL')}>
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Quantity</label>
                <input style={inputStyle} type="number" min={1} value={tradeQty} onChange={(e) => setTradeQty(e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Price (Rs.)</label>
                <input style={inputStyle} type="number" min={0} step="0.1" value={tradePrice} onChange={(e) => setTradePrice(e.target.value)} />
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <button
                style={{
                  ...buttonStyle,
                  borderColor: tradeAction === 'BUY' ? 'rgba(34,197,94,0.5)' : 'rgba(255,67,54,0.5)',
                  background: tradeAction === 'BUY' ? 'rgba(34,197,94,0.12)' : 'rgba(255,67,54,0.12)',
                  color: tradeAction === 'BUY' ? '#86efac' : '#ff6b5e',
                }}
                onClick={handleManualTrade}
                disabled={placing}
              >
                {placing ? 'Placing…' : `Place ${tradeAction} Order`}
              </button>
            </div>
            {trades.length > 0 ? (
              <div style={{ marginTop: 20 }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                  Recent trades
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 220, overflowY: 'auto' }}>
                  {[...trades].reverse().slice(0, 10).map((t) => (
                    <div key={`${t.trade_id}-${t.timestamp}`} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.8rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.5rem', border: '1px solid var(--glass-border)', fontSize: '0.8rem' }}>
                      <span style={{ color: t.action === 'BUY' ? 'var(--bullish)' : 'var(--bearish)', fontWeight: 700 }}>
                        {t.action} {t.symbol}
                      </span>
                      <span>x{t.quantity} @ Rs.{t.price}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{t.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="glass-card" style={{ marginBottom: 24 }}>
          <div className="glass-card-header">
            <div className="glass-card-title">Mero Share Portfolio</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {portfolio?.fetched_at ? `fetched ${new Date(portfolio.fetched_at).toLocaleString()}` : ''}
            </div>
          </div>
          {holdings.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No holdings yet. Connect Mero Share (live mode) or place paper trades to build a portfolio.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Symbol</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Units</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>WACC</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>LTP</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Unrealized P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => (
                    <tr key={h.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                      <td style={{ padding: '0.6rem 0.75rem', fontWeight: 700 }}>{h.symbol}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>{h.units}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>Rs. {h.wacc?.toFixed(2)}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>Rs. {h.ltp?.toFixed(2)}</td>
                      <td style={{ padding: '0.6rem 0.75rem', color: gainColor(h.unrealized_gain) }}>
                        Rs. {h.unrealized_gain?.toLocaleString()} ({h.unrealized_gain_pct >= 0 ? '+' : ''}{h.unrealized_gain_pct?.toFixed(2)}%)
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Agent Positions</div>
          </div>
          {positions.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              The agent has no open positions. Run an agent cycle to let the model scan and trade.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Symbol</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Units</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Entry</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Current</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Stop / Target</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>P&L</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => (
                    <tr key={p.symbol} style={{ borderTop: '1px solid var(--glass-border)' }}>
                      <td style={{ padding: '0.6rem 0.75rem', fontWeight: 700 }}>{p.symbol}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>{p.units}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>Rs. {p.entry_price?.toFixed(2)}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>Rs. {p.current_price?.toFixed(2)}</td>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>
                        {p.stop_loss?.toFixed(0)} / {p.target_1?.toFixed(0)}
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem', color: gainColor(p.unrealized_pnl) }}>
                        {p.unrealized_pnl_pct >= 0 ? '+' : ''}{p.unrealized_pnl_pct?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>
                        <button
                          style={{ ...buttonStyle, padding: '0.35rem 0.8rem', fontSize: '0.72rem', borderColor: 'rgba(255,67,54,0.4)', background: 'rgba(255,67,54,0.1)', color: '#ff6b5e' }}
                          onClick={() => handleExit(p.symbol)}
                        >
                          Exit
                        </button>
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
