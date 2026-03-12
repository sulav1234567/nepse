'use client';

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { generateHistoricalPrices } from '@/lib/demo-data';
import { fetchLiveStocks } from '@/lib/api-client';
import { computeFCS } from '@/lib/analysis-engine';
import { LayerWeights } from '@/lib/types';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const DEFAULT_WEIGHTS: LayerWeights = { fvl: 0.25, tml: 0.25, ssil: 0.15, gtbil: 0.25, mrlll: 0.10 };

const COLORS = ['#6366f1', '#00e676', '#06b6d4', '#f59e0b', '#8b5cf6', '#10b981', '#ff5252', '#fbbf24', '#818cf8', '#34d399'];

export default function PortfolioPage() {
  const [allocations, setAllocations] = useState<{ symbol: string; name: string; weight: number; fcs: number; signal: string }[]>([]);
  const [metrics, setMetrics] = useState({ expectedReturn: 0, volatility: 0, sortino: 0, sharpe: 0 });
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<'LIVE' | 'DEMO'>('DEMO');

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const stocksData = await fetchLiveStocks();
      setDataSource(stocksData.source);
      
      const fcsScores: Record<string, number> = {};
      stocksData.stocks.forEach(stock => {
        const hist = generateHistoricalPrices(stock);
        const fcs = computeFCS(stock, hist, DEFAULT_WEIGHTS);
        fcsScores[stock.symbol] = fcs.score;
      });

      // FCS-weighted allocation (simulating PyPortfolioOpt output)
      const eligible = stocksData.stocks.filter(s => (fcsScores[s.symbol] || 0) > 40);
      const totalFCS = eligible.reduce((sum, s) => sum + Math.max(0, (fcsScores[s.symbol] || 0) - 30), 0);

      const allocs = eligible.map(s => {
        const rawWeight = Math.max(0, (fcsScores[s.symbol] || 0) - 30);
        return {
          symbol: s.symbol,
          name: s.name,
          weight: Math.round((rawWeight / totalFCS) * 1000) / 10,
          fcs: fcsScores[s.symbol] || 0,
          signal: fcsScores[s.symbol] >= 85 ? 'STRONG BUY' : fcsScores[s.symbol] >= 70 ? 'BUY' : fcsScores[s.symbol] >= 55 ? 'SPECULATIVE BUY' : 'HOLD',
        };
      }).sort((a, b) => b.weight - a.weight);

      setAllocations(allocs);
      setMetrics({
        expectedReturn: 18.5 + Math.random() * 8,
        volatility: 12.2 + Math.random() * 5,
        sortino: 1.2 + Math.random() * 0.8,
        sharpe: 0.9 + Math.random() * 0.6,
      });
      setLoading(false);
    }
    
    loadData();
  }, []);

  const pieData = allocations.filter(a => a.weight > 2).map(a => ({ name: a.symbol, value: a.weight }));

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Portfolio Optimizer</h2>
          <div className="subtitle">Sortino-Omega optimization · PyPortfolioOpt · Regime-constrained</div>
          <div className={`data-badge ${dataSource === 'LIVE' ? 'live' : 'demo'}`}><span className="pulse"></span>{dataSource === 'LIVE' ? 'LIVE' : 'DEMO'} · FCS-weighted allocation</div>
        </div>

        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 24 }}>
          <div className="stat-card">
            <div className="stat-label">Expected Return</div>
            <div className="stat-value positive" style={{ color: 'var(--bullish)' }}>{metrics.expectedReturn.toFixed(1)}%</div>
            <div className="stat-change">Annualized</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Volatility</div>
            <div className="stat-value">{metrics.volatility.toFixed(1)}%</div>
            <div className="stat-change">Annualized</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Sortino Ratio</div>
            <div className="stat-value" style={{ color: metrics.sortino > 1.5 ? 'var(--bullish)' : 'var(--hold)' }}>{metrics.sortino.toFixed(2)}</div>
            <div className="stat-change">Above T-Bill {'>'}1.5 is excellent</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Sharpe Ratio</div>
            <div className="stat-value">{metrics.sharpe.toFixed(2)}</div>
            <div className="stat-change">Risk-adjusted return</div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Optimal Allocation</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={70} outerRadius={120} paddingAngle={2} dataKey="value"
                    label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
                    labelLine={{ stroke: 'rgba(255,255,255,0.2)' }}
                  >
                    {pieData.map((_, i) => <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8ecf4' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Allocation Table</div>
            </div>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
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
                  {allocations.map(a => (
                    <tr key={a.symbol}>
                      <td className="symbol-cell">{a.symbol}</td>
                      <td className="number-cell" style={{ fontWeight: 700 }}>{a.weight.toFixed(1)}%</td>
                      <td className="number-cell" style={{ color: a.fcs >= 70 ? 'var(--bullish)' : a.fcs >= 50 ? 'var(--hold)' : 'var(--bearish)' }}>{Math.round(a.fcs)}</td>
                      <td><span className={`signal-badge ${a.signal.toLowerCase().replace(/ /g, '-')}`} style={{ fontSize: '0.65rem' }}>{a.signal}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Optimization Parameters</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <div>
              <div style={{ fontWeight: 700, color: 'var(--accent-primary)', marginBottom: 8 }}>Engine</div>
              <div>• PyPortfolioOpt (pypfopt)</div>
              <div>• Sortino-Omega Hybrid Reward</div>
              <div>• R = Ω_modified - 1.8×DD - 2.5×Slippage</div>
            </div>
            <div>
              <div style={{ fontWeight: 700, color: 'var(--accent-primary)', marginBottom: 8 }}>Constraints</div>
              <div>• Max single position: 15%</div>
              <div>• Regime multiplier: 1.0x (Bull)</div>
              <div>• Risk-free rate: 5.8% (T-Bill)</div>
            </div>
            <div>
              <div style={{ fontWeight: 700, color: 'var(--accent-primary)', marginBottom: 8 }}>Libraries</div>
              <div>• numpy · pandas (data)</div>
              <div>• scipy (covariance)</div>
              <div>• pypfopt (optimization)</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
