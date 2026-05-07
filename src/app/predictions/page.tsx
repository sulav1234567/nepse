'use client';

import { useEffect, useState } from 'react';

import Sidebar from '@/components/Sidebar';
import {
  fetchDailyPredictions,
  fetchLiveStocks,
  fetchMonthlyPredictions,
  fetchWeeklyPredictions,
  type ApiDataSource,
} from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

type TabKey = 'daily' | 'weekly' | 'monthly';

type DailyPrediction = {
  rank: number;
  symbol: string;
  name: string;
  signal_type: string;
  entry_zone: string;
  target: number;
  stop_loss: number;
  confidence: number;
  signal: string;
  rationale: string;
};

type WeeklyPrediction = {
  symbol: string;
  name: string;
  entry_range: string;
  target_week: number;
  stop_loss: number;
  fcs: number;
  signal: string;
  time_horizon: string;
  key_driver: string;
};

type MonthlyPrediction = {
  symbol: string;
  name: string;
  entry_strategy: string;
  target_1m: number;
  target_3m: number;
  stop_loss: number;
  portfolio_weight: number;
  signal: string;
  thesis: string;
  catalyst_calendar: string;
  invalidation_conditions: string[];
};

function getSignalClass(signal: string): string {
  return signal.toLowerCase().replace(/ /g, '-');
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

export default function PredictionsPage() {
  const [tab, setTab] = useState<TabKey>('daily');
  const [daily, setDaily] = useState<DailyPrediction[]>([]);
  const [weekly, setWeekly] = useState<WeeklyPrediction[]>([]);
  const [monthly, setMonthly] = useState<MonthlyPrediction[]>([]);
  const [source, setSource] = useState<ApiDataSource>('UNKNOWN');
  const [updatedAt, setUpdatedAt] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadPredictions() {
      try {
        setLoading(true);

        const [sourceResponse, dailyResponse, weeklyResponse, monthlyResponse] = await Promise.all([
          fetchLiveStocks(),
          fetchDailyPredictions() as Promise<DailyPrediction[]>,
          fetchWeeklyPredictions() as Promise<WeeklyPrediction[]>,
          fetchMonthlyPredictions() as Promise<MonthlyPrediction[]>,
        ]);

        if (!isActive) {
          return;
        }

        setSource(sourceResponse.source);
        setDaily(dailyResponse);
        setWeekly(weeklyResponse);
        setMonthly(monthlyResponse);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError(null);
      } catch (loadError) {
        if (!isActive) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load predictions.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadPredictions();
    const interval = window.setInterval(loadPredictions, REFRESH_INTERVAL_MS);

    return () => {
      isActive = false;
      window.clearInterval(interval);
    };
  }, []);

  const cards =
    tab === 'daily'
      ? daily.map((prediction) => ({
          symbol: prediction.symbol,
          name: prediction.name,
          signal: prediction.signal,
          headline: prediction.signal_type,
          entry: prediction.entry_zone,
          target: prediction.target,
          stopLoss: prediction.stop_loss,
          score: prediction.confidence,
          note: prediction.rationale,
        }))
      : tab === 'weekly'
        ? weekly.map((prediction) => ({
            symbol: prediction.symbol,
            name: prediction.name,
            signal: prediction.signal,
            headline: prediction.key_driver,
            entry: prediction.entry_range,
            target: prediction.target_week,
            stopLoss: prediction.stop_loss,
            score: prediction.fcs,
            note: prediction.time_horizon,
          }))
        : monthly.map((prediction) => ({
            symbol: prediction.symbol,
            name: prediction.name,
            signal: prediction.signal,
            headline: prediction.catalyst_calendar,
            entry: prediction.entry_strategy,
            target: prediction.target_1m,
            stopLoss: prediction.stop_loss,
            score: prediction.portfolio_weight * 6.5,
            note: prediction.thesis,
          }));

  const tierLabel =
    tab === 'daily'
      ? 'Top 5 daily setups from the backend trade engine'
      : tab === 'weekly'
        ? 'Top 10 weekly position ideas from the backend swing engine'
        : 'Top monthly conviction names sized for portfolio inclusion';

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Predictions</h2>
          <div className="subtitle">Backend-generated daily, weekly, and monthly NEPSE trade ideas</div>
          <div className={`data-badge ${source === 'UNAVAILABLE' ? 'demo' : 'live'}`}>
            <span className="pulse"></span>
            {formatSource(source)} · refresh {REFRESH_INTERVAL_MS / 1000}s · {updatedAt || 'waiting'}
          </div>
        </div>

        <div className="tabs">
          <button className={`tab-btn ${tab === 'daily' ? 'active' : ''}`} onClick={() => setTab('daily')}>Daily</button>
          <button className={`tab-btn ${tab === 'weekly' ? 'active' : ''}`} onClick={() => setTab('weekly')}>Weekly</button>
          <button className={`tab-btn ${tab === 'monthly' ? 'active' : ''}`} onClick={() => setTab('monthly')}>Monthly</button>
        </div>

        <div style={{ marginBottom: 16, fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
          {tierLabel}
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="predictions-grid">
            {[1, 2, 3].map((card) => (
              <div key={card} className="loading-skeleton" style={{ height: 240, borderRadius: 16 }} />
            ))}
          </div>
        ) : (
          <div className="predictions-grid">
            {cards.map((prediction, index) => (
              <div key={prediction.symbol} className={`prediction-card ${getSignalClass(prediction.signal)}`}>
                <div className="rank-badge">{index + 1}</div>
                <div className="pred-header">
                  <div>
                    <div className="pred-symbol">{prediction.symbol}</div>
                    <div className="pred-name">{prediction.name}</div>
                    <div className="pred-signal-type">{prediction.headline}</div>
                  </div>
                </div>

                <div style={{ margin: '10px 0' }}>
                  <span className={`signal-badge ${getSignalClass(prediction.signal)}`}>{prediction.signal}</span>
                  <span style={{ marginLeft: 8, fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: '1rem' }}>
                    Score {Math.round(prediction.score)}
                  </span>
                </div>

                <div className="pred-metrics">
                  <div className="pred-metric">
                    <div className="pred-metric-label">Entry</div>
                    <div className="pred-metric-value">{prediction.entry}</div>
                  </div>
                  <div className="pred-metric">
                    <div className="pred-metric-label">Target</div>
                    <div className="pred-metric-value target">Rs.{prediction.target.toLocaleString()}</div>
                  </div>
                  <div className="pred-metric">
                    <div className="pred-metric-label">Stop Loss</div>
                    <div className="pred-metric-value stop">Rs.{prediction.stopLoss.toLocaleString()}</div>
                  </div>
                </div>

                <div className="pred-rationale">{prediction.note}</div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
