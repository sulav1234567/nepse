'use client';

import { useEffect, useState } from 'react';
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
import { fetchAIPredictions, fetchHealth } from '@/lib/api-client';

const REFRESH_INTERVAL_MS = 60_000;

type HealthResponse = {
  status: string;
  version: string;
  stocks_loaded: number;
  data_mode: string;
  ml_trained: boolean;
  libraries: Record<string, boolean>;
};

type AIPredictionsResponse = {
  predictions: Array<{
    symbol: string;
    riseProbability: number;
    predictedChangePercent: number;
    confidence: string;
  }>;
  modelMetrics: {
    accuracy: number;
    samples: number;
    features: number;
    training_time: number;
    positive_rate?: number;
  };
  featureImportance: Array<{
    feature: string;
    importance: number;
  }>;
};

export default function AuditPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [aiData, setAiData] = useState<AIPredictionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadAudit() {
      try {
        const [healthResponse, aiResponse] = await Promise.all([
          fetchHealth() as Promise<HealthResponse>,
          fetchAIPredictions(8) as Promise<AIPredictionsResponse>,
        ]);

        if (!isActive) {
          return;
        }

        setHealth(healthResponse);
        setAiData(aiResponse);
        setError(null);
      } catch (loadError) {
        if (!isActive) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load diagnostics.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadAudit();
    const interval = window.setInterval(loadAudit, REFRESH_INTERVAL_MS);

    return () => {
      isActive = false;
      window.clearInterval(interval);
    };
  }, []);

  const topFeatures = aiData?.featureImportance?.slice(0, 8) ?? [];
  const topPredictions = aiData?.predictions?.slice(0, 5) ?? [];

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Engine Diagnostics</h2>
          <div className="subtitle">Live backend health, model training metrics, and current feature influence</div>
          <div className="data-badge live">
            <span className="pulse"></span>
            backend audit · refresh {REFRESH_INTERVAL_MS / 1000}s
          </div>
        </div>

        {error ? (
          <div className="glass-card" style={{ marginBottom: 24, color: 'var(--bearish)' }}>
            {error}
          </div>
        ) : null}

        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 24 }}>
          <div className="stat-card">
            <div className="stat-label">Service Status</div>
            <div className="stat-value" style={{ color: 'var(--bullish)' }}>{health?.status ?? '--'}</div>
            <div className="stat-change">{health?.version ?? '--'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Stocks Loaded</div>
            <div className="stat-value">{health?.stocks_loaded ?? '--'}</div>
            <div className="stat-change">{health?.data_mode ?? '--'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Model Accuracy</div>
            <div className="stat-value">{aiData?.modelMetrics?.accuracy?.toFixed(1) ?? '--'}%</div>
            <div className="stat-change">{aiData?.modelMetrics?.samples ?? '--'} samples</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Features Used</div>
            <div className="stat-value">{aiData?.modelMetrics?.features ?? '--'}</div>
            <div className="stat-change">Current ensemble inputs</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Training Time</div>
            <div className="stat-value">{aiData?.modelMetrics?.training_time?.toFixed(2) ?? '--'}s</div>
            <div className="stat-change">{health?.ml_trained ? 'trained' : 'waiting'}</div>
          </div>
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 24 }}>
          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Top Feature Importance</div>
            </div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={1}>
                <BarChart data={topFeatures} layout="vertical">
                  <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.04)" />
                  <XAxis type="number" stroke="rgba(255,255,255,0.1)" tick={{ fill: '#5a6580', fontSize: 10 }} />
                  <YAxis type="category" dataKey="feature" width={120} stroke="rgba(255,255,255,0.1)" tick={{ fill: '#8b95b0', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#141b2d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} />
                  <Bar dataKey="importance" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card">
            <div className="glass-card-header">
              <div className="glass-card-title">Current AI Leaders</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {loading ? (
                Array.from({ length: 5 }).map((_, rowIndex) => (
                  <div key={rowIndex} className="loading-skeleton" style={{ height: 56, borderRadius: 10 }} />
                ))
              ) : (
                topPredictions.map((prediction) => (
                  <div key={prediction.symbol} style={{ padding: '0.85rem 1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.75rem', border: '1px solid var(--glass-border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '1rem', fontWeight: 700 }}>{prediction.symbol}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {prediction.confidence} confidence · {prediction.predictedChangePercent >= 0 ? '+' : ''}{prediction.predictedChangePercent.toFixed(2)}%
                        </div>
                      </div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--bullish)' }}>
                        {prediction.riseProbability.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="glass-card">
          <div className="glass-card-header">
            <div className="glass-card-title">Library Readiness</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            {Object.entries(health?.libraries ?? {}).map(([library, ready]) => (
              <div key={library} style={{ padding: '0.9rem 1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '0.75rem', border: '1px solid var(--glass-border)' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>{library}</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: ready ? 'var(--bullish)' : 'var(--bearish)' }}>
                  {ready ? 'READY' : 'OFFLINE'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
