'use client';

type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

type Guide = {
  label: string;
  value: number;
  color: string;
};

interface CandlestickChartProps {
  data: Candle[];
  height?: number;
  guides?: Guide[];
}

function formatPrice(value: number): string {
  return `Rs.${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function CandlestickChart({
  data,
  height = 320,
  guides = [],
}: CandlestickChartProps) {
  if (!data.length) {
    return (
      <div
        style={{
          minHeight: height,
          display: 'grid',
          placeItems: 'center',
          color: 'var(--text-muted)',
          border: '1px dashed var(--glass-border)',
          borderRadius: '1rem',
        }}
      >
        No candle data available.
      </div>
    );
  }

  const width = Math.max(760, data.length * 18);
  const paddingTop = 18;
  const paddingRight = 26;
  const paddingBottom = 28;
  const paddingLeft = 20;
  const innerWidth = width - paddingLeft - paddingRight;
  const innerHeight = height - paddingTop - paddingBottom;
  const values = [
    ...data.flatMap((candle) => [candle.high, candle.low]),
    ...guides.map((guide) => guide.value),
  ];
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = Math.max(maxValue - minValue, 1);
  const step = innerWidth / Math.max(data.length, 1);
  const candleWidth = Math.min(9, step * 0.56);
  const labelEvery = Math.max(1, Math.floor(data.length / 6));

  const yFor = (value: number): number => {
    const ratio = (value - minValue) / range;
    return paddingTop + innerHeight - ratio * innerHeight;
  };

  return (
    <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Candlestick chart">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const value = minValue + range * tick;
          const y = yFor(value);
          return (
            <g key={tick}>
              <line
                x1={paddingLeft}
                x2={width - paddingRight}
                y1={y}
                y2={y}
                stroke="rgba(255,255,255,0.05)"
                strokeDasharray="3 4"
              />
              <text
                x={width - paddingRight + 6}
                y={y + 4}
                fontSize="10"
                fill="#6b748c"
                textAnchor="start"
              >
                {Math.round(value)}
              </text>
            </g>
          );
        })}

        {guides.map((guide) => {
          const y = yFor(guide.value);
          return (
            <g key={guide.label}>
              <line
                x1={paddingLeft}
                x2={width - paddingRight}
                y1={y}
                y2={y}
                stroke={guide.color}
                strokeWidth="1.2"
                strokeDasharray="5 4"
                opacity="0.9"
              />
              <text
                x={paddingLeft + 8}
                y={y - 6}
                fontSize="10"
                fill={guide.color}
              >
                {guide.label}
              </text>
            </g>
          );
        })}

        {data.map((candle, index) => {
          const x = paddingLeft + index * step + step / 2;
          const openY = yFor(candle.open);
          const closeY = yFor(candle.close);
          const highY = yFor(candle.high);
          const lowY = yFor(candle.low);
          const bullish = candle.close >= candle.open;
          const bodyTop = Math.min(openY, closeY);
          const bodyHeight = Math.max(1.6, Math.abs(closeY - openY));
          const color = bullish ? '#18c47c' : '#ef4444';

          return (
            <g key={`${candle.date}-${index}`}>
              <line
                x1={x}
                x2={x}
                y1={highY}
                y2={lowY}
                stroke={color}
                strokeWidth="1.2"
              />
              <rect
                x={x - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                rx="1"
                fill={bullish ? `${color}CC` : `${color}BB`}
                stroke={color}
                strokeWidth="1"
              />
              {index % labelEvery === 0 || index === data.length - 1 ? (
                <text
                  x={x}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#6b748c"
                >
                  {candle.date.slice(5)}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>

      <div
        style={{
          display: 'flex',
          gap: 16,
          marginTop: 10,
          flexWrap: 'wrap',
          color: 'var(--text-secondary)',
          fontSize: '0.72rem',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: '#18c47c' }} />
          Bullish candle
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: '#ef4444' }} />
          Bearish candle
        </span>
        {guides.slice(0, 2).map((guide) => (
          <span key={guide.label} style={{ color: guide.color }}>
            {guide.label}: {formatPrice(guide.value)}
          </span>
        ))}
      </div>
    </div>
  );
}
