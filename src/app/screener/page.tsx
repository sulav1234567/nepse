'use client';

import { useState, useEffect, useMemo } from 'react';
import Sidebar from '@/components/Sidebar';
import { generateHistoricalPrices } from '@/lib/demo-data';
import { fetchLiveStocks } from '@/lib/api-client';
import { computeFCS } from '@/lib/analysis-engine';
import { LayerWeights, Stock, Sector } from '@/lib/types';
import Link from 'next/link';

const DEFAULT_WEIGHTS: LayerWeights = { fvl: 0.25, tml: 0.25, ssil: 0.15, gtbil: 0.25, mrlll: 0.10 };

const SECTORS: (Sector | 'All')[] = ['All', 'Commercial Bank', 'Development Bank', 'Hydropower', 'Insurance', 'Microfinance', 'Manufacturing', 'Hotel & Tourism'];

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

function getScoreColor(score: number): string {
  if (score >= 70) return 'high';
  if (score >= 45) return 'medium';
  return 'low';
}

interface StockRow {
  stock: Stock;
  fcs: number;
  signal: string;
  fvl: number;
  tml: number;
  ssil: number;
  gtbil: number;
  mrlll: number;
}

export default function ScreenerPage() {
  const [rows, setRows] = useState<StockRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<'LIVE' | 'DEMO'>('DEMO');
  const [sector, setSector] = useState<Sector | 'All'>('All');
  const [sortKey, setSortKey] = useState<string>('fcs');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const stocksData = await fetchLiveStocks();
      setDataSource(stocksData.source);
      
      const results: StockRow[] = stocksData.stocks.map(stock => {
        const history = generateHistoricalPrices(stock);
        const fcs = computeFCS(stock, history, DEFAULT_WEIGHTS);
        return {
          stock,
          fcs: fcs.score,
          signal: fcs.signal,
          fvl: fcs.layerScores.fvl,
          tml: fcs.layerScores.tml,
          ssil: fcs.layerScores.ssil,
          gtbil: fcs.layerScores.gtbil,
          mrlll: fcs.layerScores.mrlll,
        };
      });
      setRows(results);
      setLoading(false);
    }
    
    loadData();
    
    // Note: Data is fetched once on mount. To refresh, user can reload the page.
    // Future enhancement: Add a refresh button or auto-refresh timer
  }, []);

  const filtered = useMemo(() => {
    let data = sector === 'All' ? rows : rows.filter(r => r.stock.sector === sector);
    data.sort((a, b) => {
      const aVal = (a as any)[sortKey] ?? (a.stock as any)[sortKey] ?? 0;
      const bVal = (b as any)[sortKey] ?? (b.stock as any)[sortKey] ?? 0;
      return sortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });
    return data;
  }, [rows, sector, sortKey, sortDir]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const thClass = (key: string) => sortKey === key ? 'sorted' : '';

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Stock Screener</h2>
          <div className="subtitle">Five-layer analysis scores for all NEPSE stocks</div>
          <div className={`data-badge ${dataSource === 'LIVE' ? 'live' : 'demo'}`}>
            <span className="pulse"></span>
            {dataSource === 'LIVE' ? 'LIVE DATA' : 'DEMO DATA'} · {rows.length} stocks loaded
          </div>
        </div>

        <div className="sector-chips">
          {SECTORS.map(s => (
            <button key={s} className={`sector-chip ${sector === s ? 'active' : ''}`} onClick={() => setSector(s)}>
              {s}
            </button>
          ))}
        </div>

        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('symbol')} className={thClass('symbol')}>Symbol</th>
                <th>Name</th>
                <th>Sector</th>
                <th onClick={() => handleSort('cmp')} className={thClass('cmp')}>CMP</th>
                <th onClick={() => handleSort('changePercent')} className={thClass('changePercent')}>Chg%</th>
                <th onClick={() => handleSort('pe')} className={thClass('pe')}>P/E</th>
                <th onClick={() => handleSort('pb')} className={thClass('pb')}>P/B</th>
                <th onClick={() => handleSort('roe')} className={thClass('roe')}>ROE%</th>
                <th onClick={() => handleSort('fvl')} className={thClass('fvl')}>FVL</th>
                <th onClick={() => handleSort('tml')} className={thClass('tml')}>TML</th>
                <th onClick={() => handleSort('ssil')} className={thClass('ssil')}>SSIL</th>
                <th onClick={() => handleSort('gtbil')} className={thClass('gtbil')}>GTBIL</th>
                <th onClick={() => handleSort('mrlll')} className={thClass('mrlll')}>MRLLL</th>
                <th onClick={() => handleSort('fcs')} className={thClass('fcs')}>FCS</th>
                <th>Signal</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 15 }).map((_, j) => (
                      <td key={j}><div className="loading-skeleton" style={{ height: 16, width: j < 3 ? 80 : 48 }} /></td>
                    ))}
                  </tr>
                ))
              ) : filtered.map(row => (
                <tr key={row.stock.symbol}>
                  <td className="symbol-cell">
                    <Link href={`/analysis?symbol=${row.stock.symbol}`} style={{ color: 'inherit' }}>
                      {row.stock.symbol}
                    </Link>
                  </td>
                  <td className="name-cell">{row.stock.name}</td>
                  <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{row.stock.sector}</td>
                  <td className="number-cell">Rs.{row.stock.cmp.toLocaleString()}</td>
                  <td className={`number-cell ${row.stock.changePercent >= 0 ? 'positive' : 'negative'}`}>
                    {row.stock.changePercent >= 0 ? '+' : ''}{row.stock.changePercent.toFixed(2)}%
                  </td>
                  <td className="number-cell">{row.stock.pe.toFixed(1)}</td>
                  <td className="number-cell">{row.stock.pb.toFixed(2)}</td>
                  <td className="number-cell">{row.stock.roe.toFixed(1)}</td>
                  {['fvl', 'tml', 'ssil', 'gtbil', 'mrlll'].map(layer => {
                    const val = (row as any)[layer] as number;
                    return (
                      <td key={layer}>
                        <div className="layer-score">
                          <div className="layer-score-bar">
                            <div className={`layer-score-fill ${getScoreColor(val)}`} style={{ width: `${val}%` }} />
                          </div>
                          <span style={{ fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: val >= 65 ? 'var(--bullish)' : val >= 45 ? 'var(--hold)' : 'var(--bearish)' }}>
                            {Math.round(val)}
                          </span>
                        </div>
                      </td>
                    );
                  })}
                  <td className="number-cell" style={{ fontWeight: 800, fontSize: '0.9rem', color: row.fcs >= 70 ? 'var(--bullish)' : row.fcs >= 50 ? 'var(--hold)' : 'var(--bearish)' }}>
                    {Math.round(row.fcs)}
                  </td>
                  <td><span className={`signal-badge ${getSignalClass(row.signal)}`}>{row.signal}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
