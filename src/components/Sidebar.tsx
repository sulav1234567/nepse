'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { ApiMarketIntelligenceResponse, fetchMarketIntelligence } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const isActive = (path: string) => pathname === path ? 'active' : '';
  const [marketIntel, setMarketIntel] = useState<ApiMarketIntelligenceResponse | null>(null);

  const handleLogout = () => {
    logout();
    router.push('/auth/login');
  };

  useEffect(() => {
    let active = true;

    async function loadMarketIntel() {
      try {
        const response = await fetchMarketIntelligence();
        if (active) {
          setMarketIntel(response);
        }
      } catch {
        if (active) {
          setMarketIntel(null);
        }
      }
    }

    loadMarketIntel();
    const interval = window.setInterval(loadMarketIntel, 60_000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const regimeLabel = marketIntel?.market.regime ?? 'Waiting...';
  const regimeConfidence = Math.max(8, Math.min(100, Math.round(marketIntel?.market.regime_confidence ?? 18)));
  const crashRisk = marketIntel?.intelligence.crash_risk;

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>NEPSE-ALPHA</h1>
        <div className="version-tag">ULTIMATE v1.0 · Five-Layer Engine</div>
      </div>

      <div className="regime-sidebar">
        <div className="regime-label">Market Regime</div>
        <div className="regime-value">{regimeLabel}</div>
        <div className="regime-confidence">
          <div className="regime-confidence-fill" style={{ width: `${regimeConfidence}%` }}></div>
        </div>
        <div style={{ marginTop: 8, fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          {marketIntel?.intelligence.bias ?? 'SCANNING'} · crash risk {crashRisk?.toFixed(0) ?? '--'}%
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Dashboard</div>
        <Link href="/" className={isActive('/')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
          </svg>
          Overview
        </Link>

        <div className="sidebar-section-label">Analysis</div>
        <Link href="/screener" className={isActive('/screener')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          Stock Screener
        </Link>
        <Link href="/predictions" className={isActive('/predictions')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
          </svg>
          Predictions
        </Link>

        <div className="sidebar-section-label">Intelligence</div>
        <Link href="/ai-predictions" className={isActive('/ai-predictions')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a4 4 0 0 0-4 4c0 2.5 2 3.5 2 5h4c0-1.5 2-2.5 2-5a4 4 0 0 0-4-4z" /><path d="M10 17v1a2 2 0 1 0 4 0v-1" /><line x1="12" y1="11" x2="12" y2="11.01" />
          </svg>
          AI Predictions
        </Link>
        <Link href="/autonomous" className={isActive('/autonomous')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v4" /><path d="M12 18v4" /><path d="M4.93 4.93l2.83 2.83" /><path d="M16.24 16.24l2.83 2.83" /><path d="M2 12h4" /><path d="M18 12h4" /><path d="M4.93 19.07l2.83-2.83" /><path d="M16.24 7.76l2.83-2.83" /><circle cx="12" cy="12" r="4" />
          </svg>
          Autonomous AI
        </Link>
        <Link href="/recommendations" className={isActive('/recommendations')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" /><path d="M12 4h9" /><path d="M4 9l3 3 5-5" /><path d="M4 17l3 3 5-5" />
          </svg>
          Recommendations
        </Link>
        <Link href="/analysis" className={isActive('/analysis')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
          </svg>
          Deep Analysis
        </Link>
        <Link href="/candlestick-analysis" className={isActive('/candlestick-analysis')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 3v18" /><rect x="4" y="7" width="4" height="6" /><path d="M12 3v18" /><rect x="10" y="4" width="4" height="10" /><path d="M18 3v18" /><rect x="16" y="11" width="4" height="6" />
          </svg>
          Candle Analysis
        </Link>
        <Link href="/index-analysis" className={isActive('/index-analysis')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3v18h18" /><path d="M7 14l3-3 3 2 5-6" />
          </svg>
          NEPSE Index
        </Link>
        <Link href="/portfolio" className={isActive('/portfolio')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          </svg>
          Portfolio Optimizer
        </Link>

        <div className="sidebar-section-label">Trading</div>
        <Link href="/trader" className={isActive('/trader')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
          Broker Trading
        </Link>

        <div className="sidebar-section-label">System</div>
        <Link href="/audit" className={isActive('/audit')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          Self-Audit
        </Link>
      </nav>

      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border-subtle)' }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
          Engine: numpy · scipy · filterpy<br/>
          Models: K-Means · Kalman · BSTS<br/>
          Data: LIVE MODE
        </div>
      </div>

      {user && (
        <div style={{ 
          padding: '16px 20px', 
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px'
        }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ 
              fontSize: '0.75rem', 
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Logged In
            </div>
            <div style={{ 
              fontSize: '0.85rem', 
              fontWeight: '500',
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {user.username}
            </div>
          </div>
          <button
            onClick={handleLogout}
            style={{
              padding: '6px 10px',
              fontSize: '0.7rem',
              background: 'rgba(255, 67, 54, 0.1)',
              color: '#ff4336',
              border: '1px solid rgba(255, 67, 54, 0.3)',
              borderRadius: '4px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              fontWeight: '500',
              whiteSpace: 'nowrap',
              flex: '0 0 auto'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 67, 54, 0.2)';
              e.currentTarget.style.borderColor = 'rgba(255, 67, 54, 0.5)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 67, 54, 0.1)';
              e.currentTarget.style.borderColor = 'rgba(255, 67, 54, 0.3)';
            }}
          >
            Logout
          </button>
        </div>
      )}
    </aside>
  );
}
