'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Sidebar() {
  const pathname = usePathname();
  const isActive = (path: string) => pathname === path ? 'active' : '';

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>NEPSE-ALPHA</h1>
        <div className="version-tag">ULTIMATE v1.0 · Five-Layer Engine</div>
      </div>

      <div className="regime-sidebar">
        <div className="regime-label">Market Regime</div>
        <div className="regime-value">BULL TREND</div>
        <div className="regime-confidence">
          <div className="regime-confidence-fill" style={{ width: '72%' }}></div>
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
        <Link href="/analysis" className={isActive('/analysis')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
          </svg>
          Deep Analysis
        </Link>
        <Link href="/portfolio" className={isActive('/portfolio')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          </svg>
          Portfolio Optimizer
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
          Data: DEMO MODE
        </div>
      </div>
    </aside>
  );
}
