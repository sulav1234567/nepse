'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

import Sidebar from '@/components/Sidebar';
import { ApiDataSource, ApiStock, fetchStocks } from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

const SECTORS = [
  'All',
  'Commercial Bank',
  'Development Bank',
  'Hydropower',
  'Insurance',
  'Microfinance',
  'Manufacturing',
  'Hotel & Tourism',
] as const;

type SectorFilter = (typeof SECTORS)[number];
type SortKey =
  | 'symbol'
  | 'cmp'
  | 'change_percent'
  | 'pe'
  | 'pb'
  | 'roe'
  | 'fvl'
  | 'tml'
  | 'ssil'
  | 'gtbil'
  | 'mrlll'
  | 'fcs';

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
}

function getScoreColor(score: number): string {
  if (score >= 70) return 'high';
  if (score >= 45) return 'medium';
  return 'low';
}

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

export default function ScreenerPage() {
  const [rows, setRows] = useState<ApiStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<ApiDataSource>('UNKNOWN');
  const [sector, setSector] = useState<SectorFilter>('All');
  const [sortKey, setSortKey] = useState<SortKey>('fcs');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    let isActive = true;

    async function loadScreener() {
      try {
        const response = await fetchStocks();
        if (!isActive) {
          return;
        }

        setRows(response.stocks);
        setSource(response.source);
        setError(null);
      } catch (loadError) {
        if (!isActive) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load screener data.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadScreener();
    const interval = window.setInterval(loadScreener, REFRESH_INTERVAL_MS);

    return () => {
      isActive = false;
      window.clearInterval(interval);
    };
  }, []);

  const filtered = useMemo(() => {
    const scoped = sector === 'All' ? [...rows] : rows.filter((row) => row.sector === sector);
    scoped.sort((left, right) => {
      const leftValue = left[sortKey];
      const rightValue = right[sortKey];
      if (typeof leftValue === 'string' && typeof rightValue === 'string') {
        return sortDir === 'desc' ? rightValue.localeCompare(leftValue) : leftValue.localeCompare(rightValue);
      }

      return sortDir === 'desc'
        ? Number(rightValue) - Number(leftValue)
        : Number(leftValue) - Number(rightValue);
    });
    return scoped;
  }, [rows, sector, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((direction) => (direction === 'desc' ? 'asc' : 'desc'));
      return;
    }

    setSortKey(key);
    setSortDir('desc');
  };

  const thClass = (key: SortKey) => (sortKey === key ? 'sorted' : '');

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Stock Screener</h2>
          <div className="subtitle">Backend-scored five-layer rankings for the live NEPSE universe</div>
          <div className={`data-badge ${source === 'UNAVAILABLE' ? 'demo' : 'live'}`}>
            <span className="pulse"></span>
            {formatSource(source)} · {rows.length} stocks · refresh {REFRESH_INTERVAL_MS / 1000}s
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div className="sector-chips">
          {SECTORS.map((value) => (
            <button key={value} className={`sector-chip ${sector === value ? 'active' : ''}`} onClick={() => setSector(value)}>
              {value}
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
                <th onClick={() => handleSort('change_percent')} className={thClass('change_percent')}>Chg%</th>
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
                Array.from({ length: 8 }).map((_, rowIndex) => (
                  <tr key={rowIndex}>
                    {Array.from({ length: 15 }).map((_, cellIndex) => (
                      <td key={cellIndex}>
                        <div className="loading-skeleton" style={{ height: 16, width: cellIndex < 3 ? 80 : 48 }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : (
                filtered.map((row) => (
                  <tr key={row.symbol}>
                    <td className="symbol-cell">
                      <Link href={`/analysis?symbol=${row.symbol}`} style={{ color: 'inherit' }}>
                        {row.symbol}
                      </Link>
                    </td>
                    <td className="name-cell">{row.name}</td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{row.sector}</td>
                    <td className="number-cell">Rs.{row.cmp.toLocaleString()}</td>
                    <td className={`number-cell ${row.change_percent >= 0 ? 'positive' : 'negative'}`}>
                      {row.change_percent >= 0 ? '+' : ''}{row.change_percent.toFixed(2)}%
                    </td>
                    <td className="number-cell">{row.pe.toFixed(1)}</td>
                    <td className="number-cell">{row.pb.toFixed(2)}</td>
                    <td className="number-cell">{row.roe.toFixed(1)}</td>
                    {(['fvl', 'tml', 'ssil', 'gtbil', 'mrlll'] as const).map((layer) => (
                      <td key={layer}>
                        <div className="layer-score">
                          <div className="layer-score-bar">
                            <div className={`layer-score-fill ${getScoreColor(row[layer])}`} style={{ width: `${row[layer]}%` }} />
                          </div>
                          <span style={{ fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                            {Math.round(row[layer])}
                          </span>
                        </div>
                      </td>
                    ))}
                    <td className="number-cell" style={{ fontWeight: 800, fontSize: '0.9rem' }}>
                      {Math.round(row.fcs)}
                    </td>
                    <td>
                      <span className={`signal-badge ${getSignalClass(row.signal)}`}>{row.signal}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
