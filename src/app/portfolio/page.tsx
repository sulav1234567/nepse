'use client';

import { useEffect, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import Sidebar from '@/components/Sidebar';
import { ApiDataSource, ApiStock, fetchPortfolio, fetchStocks } from '@/lib/api-client';

const COLORS = ['#6366f1', '#00e676', '#06b6d4', '#f59e0b', '#8b5cf6', '#10b981', '#ff5252', '#fbbf24'];
const REFRESH_INTERVAL_MS = 60_000;

type PortfolioResponse = {
  weights: Record<string, number>;
  expected_return: number;
  expected_volatility: number;
  sortino_ratio: number;
  sharpe_ratio: number;
};

type AllocationRow = {
  symbol: string;
  name: string;
  weight: number;
  fcs: number;
  signal: string;
};

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

export default function PortfolioPage() {
  const [allocations, setAllocations] = useState<AllocationRow[]>([]);
  const [metrics, setMetrics] = useState<PortfolioResponse | null>(null);
  const [source, setSource] = useState<ApiDataSource>('UNKNOWN');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadPortfolio() {
      try {
        const [portfolioResponse, stocksResponse] = await Promise.all([
          fetchPortfolio() as Promise<PortfolioResponse>,
          fetchStocks(undefined, 'fcs'),
        ]);

        if (!isActive) {
          return;
        }

        const stockIndex = new Map<string, ApiStock>(
          stocksResponse.stocks.map((stock) => [stock.symbol, stock]),
        );

        const rows = Object.entries(portfolioResponse.weights)
          .map(([symbol, weight]) => {
            const stock = stockIndex.get(symbol);
            return {
              symbol,
              name: stock?.name ?? symbol,
              weight: weight * 100,
              fcs: stock?.fcs ?? 0,
              signal: stock?.signal ?? 'HOLD',
            };
          })
          .filter((row) => row.weight > 0)
          .sort((left, right) => right.weight - left.weight);

        setAllocations(rows);
        setMetrics(portfolioResponse);
        setSource(stocksResponse.source);
        setError(null);
      } catch (loadError) {
        if (!isActive) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load portfolio.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadPortfolio();
    const interval = window.setInterval(loadPortfolio, REFRESH_INTERVAL_MS);

    return () => {
      isActive = false;
      window.clearInterval(interval);
    };
  }, []);

  const pieData = allocations.filter((allocation) => allocation.weight > 1.5).map((allocation) => ({
    name: allocation.symbol,
    value: Number(allocation.weight.toFixed(2)),
  }));

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Portfolio Optimizer</h2>
          <div className="subtitle">Backend-generated allocation using current FCS scores and regime-adjusted risk</div>
          <div className={`data-badge ${source === 'UNAVAILABLE' ? 'demo' : 'live'}`}>
            <span className="pulse"></span>
            {formatSource(source)} · refresh {REFRESH_INTERVAL_MS / 1000}s
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 24 }}>
          <div className="stat-card">
            <div className="stat-label">Expected Return</div>
            <div className="stat-value" style={{ color: 'var(--bullish)' }}>{metrics?.expected_return?.toFixed(2) ?? '--'}%</div>
            <div className="stat-change">Annualized</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Volatility</div>
            <div className="stat-value">{metrics?.expected_volatility?.toFixed(2) ?? '--'}%</div>
            <div className="stat-change">Annualized</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Sortino Ratio</div>
            <div className="stat-value" style={{ color: 'var(--bullish)' }}>{metrics?.sortino_ratio?.toFixed(2) ?? '--'}</div>
            <div className="stat-change">Downside-aware return</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Sharpe Ratio</div>
            <div className="stat-value">{metrics?.sharpe_ratio?.toFixed(2) ?? '--'}</div>
            <div className="stat-change">Risk-adjusted return</div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Optimal Allocation</div>
            </div>
            <div style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={70}
                    outerRadius={120}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
                    labelLine={{ stroke: 'rgba(255,255,255,0.2)' }}
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Allocation Table</div>
            </div>
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Weight</th>
                    <th>FCS</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    Array.from({ length: 6 }).map((_, rowIndex) => (
                      <tr key={rowIndex}>
                        {Array.from({ length: 4 }).map((_, cellIndex) => (
                          <td key={cellIndex}>
                            <div className="loading-skeleton" style={{ height: 16, width: 80 }} />
                          </td>
                        ))}
                      </tr>
                    ))
                  ) : (
                    allocations.map((allocation) => (
                      <tr key={allocation.symbol}>
                        <td className="symbol-cell">{allocation.symbol}</td>
                        <td className="number-cell" style={{ fontWeight: 700 }}>{allocation.weight.toFixed(2)}%</td>
                        <td className="number-cell">{Math.round(allocation.fcs)}</td>
                        <td>
                          <span className={`signal-badge ${allocation.signal.toLowerCase().replace(/ /g, '-')}`} style={{ fontSize: '0.65rem' }}>
                            {allocation.signal}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
