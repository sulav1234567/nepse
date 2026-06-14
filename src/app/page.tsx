'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import Sidebar from '@/components/Sidebar';
import { useAuth } from '@/lib/auth-context';
import {
  ApiDataSource,
  ApiMarket,
  ApiMarketIntelligence,
  ApiMarketIntelligenceResponse,
  ApiSector,
  ApiStock,
  fetchMarketIntelligence,
  fetchSectors,
  fetchStocks,
} from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

function formatSource(source: ApiDataSource): string {
  switch (source) {
    case 'LIVE':
      return 'NEPSE API';
    case 'LIVE_SCRAPED':
      return 'Sharesansar';
    case 'LIVE_SCRAPED_MEROLAGANI':
      return 'Merolagani';
    case 'UNAVAILABLE':
      return 'Unavailable';
    default:
      return 'Unknown';
  }
}

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  // Initialize all state hooks BEFORE any conditional returns
  const [stocks, setStocks] = useState<ApiStock[]>([]);
  const [market, setMarket] = useState<ApiMarket | null>(null);
  const [marketIntel, setMarketIntel] = useState<ApiMarketIntelligence | null>(null);
  const [sectors, setSectors] = useState<ApiSector[]>([]);
  const [source, setSource] = useState<ApiDataSource>('UNKNOWN');
  const [updatedAt, setUpdatedAt] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Send guests to the public landing page (which links to login/register).
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/landing');
    }
  }, [isAuthenticated, isLoading, router]);

  // Load dashboard data - MUST be before early returns
  useEffect(() => {
    if (!isAuthenticated || isLoading) {
      return;
    }

    let isActive = true;

    async function loadDashboard() {
      try {
        const [stocksResponse, marketResponse, sectorsResponse] = await Promise.all([
          fetchStocks(undefined, 'fcs'),
          fetchMarketIntelligence(),
          fetchSectors().catch(() => []),
        ]);

        if (!isActive) {
          return;
        }

        setStocks(stocksResponse.stocks);
        setMarket((marketResponse as ApiMarketIntelligenceResponse).market);
        setMarketIntel((marketResponse as ApiMarketIntelligenceResponse).intelligence);
        setSectors(sectorsResponse);
        setSource((marketResponse as ApiMarketIntelligenceResponse).source ?? stocksResponse.source);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError(null);
      } catch (loadError) {
        if (!isActive) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load dashboard data.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadDashboard();
    const interval = window.setInterval(loadDashboard, REFRESH_INTERVAL_MS);

    return () => {
      isActive = false;
      window.clearInterval(interval);
    };
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <div style={{ fontSize: '18px', color: '#666' }}>Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect to login
  }

  const topPicks = stocks.slice(0, 5);
  const topMovers = [...stocks]
    .sort((left, right) => right.change_percent - left.change_percent)
    .slice(0, 8)
    .map((stock) => ({
      symbol: stock.symbol,
      change: Number(stock.change_percent.toFixed(2)),
    }));
  const sectorData = sectors.map((sector) => ({
    name: sector.sector.replace(' & ', '/').slice(0, 12),
    change: Number(sector.change_percent.toFixed(2)),
  }));
  const hasVerifiedIndex = (market?.nepse_index ?? 0) > 0;
  const leaders = marketIntel?.sector_leaders?.slice(0, 3) ?? [];
  const warnings = marketIntel?.warnings?.slice(0, 3) ?? [];

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Market Intelligence Dashboard</h2>
          <div className="subtitle">Real-time NEPSE snapshot with backend-scored leaders</div>
          <div className={`data-badge ${source === 'UNAVAILABLE' ? 'demo' : 'live'}`}>
            <span className="pulse"></span>
            {formatSource(source)} · refresh {REFRESH_INTERVAL_MS / 1000}s · {updatedAt || 'waiting'}
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">NEPSE Index</div>
            <div className="stat-value">{hasVerifiedIndex ? market?.nepse_index.toLocaleString() : '--'}</div>
            <div className={`stat-change ${hasVerifiedIndex && (market?.nepse_change_percent ?? 0) >= 0 ? 'positive' : 'negative'}`}>
              {hasVerifiedIndex
                ? `${(market?.nepse_change_percent ?? 0) >= 0 ? '▲' : '▼'} ${Math.abs(market?.nepse_change ?? 0).toFixed(2)} (${Math.abs(market?.nepse_change_percent ?? 0).toFixed(2)}%)`
                : 'Waiting for verified index feed'}
            </div>
            {hasVerifiedIndex ? (
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 6 }}>
                {market?.is_live
                  ? '🟢 LIVE · market open'
                  : market?.is_stale
                    ? '🟠 Last known (live feed unreachable)'
                    : '⚪ Market closed'}
                {market?.as_of ? ` · as of ${market.as_of}` : ''}
              </div>
            ) : null}
          </div>
          <div className="stat-card">
            <div className="stat-label">Turnover</div>
            <div className="stat-value">Rs.{((market?.total_turnover ?? 0) / 1e9).toFixed(2)}B</div>
            <div className="stat-change positive">Volume {((market?.total_volume ?? 0) / 1e6).toFixed(1)}M</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Breadth</div>
            <div className="stat-value" style={{ color: (market?.advancers ?? 0) >= (market?.decliners ?? 0) ? 'var(--bullish)' : 'var(--bearish)' }}>
              {market?.advancers ?? 0}/{market?.decliners ?? 0}
            </div>
            <div className="stat-change">{market?.unchanged ?? 0} unchanged</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Market Bias</div>
            <div className="stat-value" style={{ fontSize: '1.2rem' }}>{marketIntel?.bias ?? market?.regime ?? '--'}</div>
            <div className="stat-change">{marketIntel?.action ?? `Confidence ${(market?.regime_confidence ?? 0).toFixed(0)}%`}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Crash Risk</div>
            <div className="stat-value" style={{ color: (marketIntel?.crash_risk ?? 0) >= 60 ? 'var(--bearish)' : 'var(--bullish)' }}>
              {marketIntel?.crash_risk?.toFixed(0) ?? '--'}%
            </div>
            <div className="stat-change">{marketIntel?.crash_level ?? '--'} · 91D T-Bill {market?.t_bill_yield?.toFixed(2) ?? '--'}%</div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">NEPSE Analysis Engine</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 18 }}>
              {[
                { label: 'TREND', value: `${marketIntel?.trend_score?.toFixed(0) ?? '--'}/100`, sub: `${marketIntel?.bull_probability?.toFixed(0) ?? '--'}% bull probability` },
                { label: 'LIQUIDITY', value: `${marketIntel?.liquidity_score?.toFixed(0) ?? '--'}/100`, sub: `Interbank ${(market?.interbank_rate ?? 0).toFixed(2)}%` },
                { label: 'VOLATILITY', value: `${marketIntel?.volatility_score?.toFixed(0) ?? '--'}/100`, sub: `${marketIntel?.dispersion?.toFixed(2) ?? '--'} dispersion` },
                { label: 'SUPPORT / RES.', value: hasVerifiedIndex ? `${Math.round(marketIntel?.support_low ?? 0)}-${Math.round(marketIntel?.resistance_high ?? 0)}` : '--', sub: 'Index tactical band' },
              ].map((item) => (
                <div key={item.label} style={{ padding: '0.9rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                  <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 6 }}>{item.label}</div>
                  <div style={{ fontSize: '1rem', fontWeight: 700 }}>{item.value}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: 6 }}>{item.sub}</div>
                </div>
              ))}
            </div>

            <div style={{ display: 'grid', gap: 10 }}>
              {(marketIntel?.opportunities ?? []).map((note) => (
                <div key={note} style={{ padding: '0.9rem 1rem', borderRadius: '0.85rem', background: 'rgba(24,196,124,0.06)', border: '1px solid rgba(24,196,124,0.15)', color: 'var(--text-secondary)' }}>
                  {note}
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Risk Warnings & Leaders</div>
            </div>
            <div style={{ display: 'grid', gap: 12, marginBottom: 16 }}>
              {warnings.length ? warnings.map((warning) => (
                <div key={warning.title} style={{ padding: '0.95rem 1rem', borderRadius: '0.85rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.14)' }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>{warning.title}</div>
                  <div style={{ color: 'var(--text-secondary)', lineHeight: 1.55 }}>{warning.message}</div>
                </div>
              )) : (
                <div style={{ padding: '0.95rem 1rem', borderRadius: '0.85rem', background: 'rgba(24,196,124,0.06)', border: '1px solid rgba(24,196,124,0.15)', color: 'var(--text-secondary)' }}>
                  No immediate crash symptoms are dominant in the current snapshot.
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gap: 10 }}>
              {leaders.map((leader) => (
                <div key={leader.sector} style={{ padding: '0.9rem 1rem', borderRadius: '0.85rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ fontWeight: 700 }}>{leader.sector}</div>
                    <div style={{ color: leader.avg_change >= 0 ? 'var(--bullish)' : 'var(--bearish)' }}>
                      {leader.avg_change >= 0 ? '+' : ''}{leader.avg_change.toFixed(2)}%
                    </div>
                  </div>
                  <div style={{ marginTop: 6, color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                    Breadth {leader.breadth.toFixed(0)}% · score {leader.leadership_score.toFixed(1)} · {leader.count} stocks
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Top Movers</div>
            </div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                <BarChart data={topMovers}>
                  <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="symbol" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#8b95b0', fontSize: 10 }} />
                  <YAxis stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                  <Bar dataKey="change" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Sector Performance</div>
            </div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                <BarChart data={sectorData} layout="vertical">
                  <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.04)" />
                  <XAxis type="number" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={90} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#8b95b0', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                  <Bar dataKey="change" radius={[0, 4, 4, 0]} fill="#6366f1" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Top 5 Composite Picks</div>
            <a href="/predictions" style={{ fontSize: '0.78rem', fontWeight: 600 }}>View tiers →</a>
          </div>

          {loading ? (
            <div style={{ display: 'flex', gap: 16 }}>
              {[1, 2, 3, 4, 5].map((card) => (
                <div key={card} className="loading-skeleton" style={{ height: 150, flex: 1, borderRadius: 12 }} />
              ))}
            </div>
          ) : (
            <div className="predictions-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
              {topPicks.map((stock, index) => (
                <div key={stock.symbol} className={`prediction-card ${getSignalClass(stock.signal)}`}>
                  <div className="rank-badge">{index + 1}</div>
                  <div className="pred-header">
                    <div>
                      <div className="pred-symbol">{stock.symbol}</div>
                      <div className="pred-name" style={{ maxWidth: 120 }}>{stock.name}</div>
                    </div>
                  </div>

                  <div style={{ margin: '10px 0' }}>
                    <span className={`signal-badge ${getSignalClass(stock.signal)}`}>{stock.signal}</span>
                    <span style={{ marginLeft: 8, fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: '1rem' }}>
                      FCS {Math.round(stock.fcs)}
                    </span>
                  </div>

                  <div className="pred-metrics">
                    <div className="pred-metric">
                      <div className="pred-metric-label">CMP</div>
                      <div className="pred-metric-value">Rs.{stock.cmp.toLocaleString()}</div>
                    </div>
                    <div className="pred-metric">
                      <div className="pred-metric-label">Chg%</div>
                      <div className={`pred-metric-value ${stock.change_percent >= 0 ? 'target' : 'stop'}`}>
                        {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent.toFixed(2)}%
                      </div>
                    </div>
                    <div className="pred-metric">
                      <div className="pred-metric-label">Volume</div>
                      <div className="pred-metric-value">{stock.volume.toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
