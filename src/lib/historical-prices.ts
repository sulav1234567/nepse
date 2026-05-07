/**
 * Synthetic historical price generator for technical analysis.
 * Generates 60 days of OHLCV data based on current stock metrics.
 * Used when real historical data is unavailable from the API.
 */

import { Stock, HistoricalPrice } from './types';
import { createSeededRandom } from './deterministic';

const SECTOR_VOLATILITY: Record<string, number> = {
  Hydropower: 0.035,
  'Commercial Bank': 0.018,
  'Development Bank': 0.022,
  Insurance: 0.022,
  Microfinance: 0.028,
  Manufacturing: 0.015,
  'Hotel & Tourism': 0.030,
};

export function generateHistoricalPrices(stock: Stock, days = 60): HistoricalPrice[] {
  const data: HistoricalPrice[] = [];
  let basePrice = stock.cmp * 0.85;
  const volatility = SECTOR_VOLATILITY[stock.sector] ?? 0.025;
  const random = createSeededRandom([
    stock.symbol,
    stock.cmp,
    stock.previousClose,
    stock.volume,
    stock.high52w,
    stock.low52w,
    days,
  ].join(':'));

  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    if (date.getDay() === 6) continue; // Skip Saturday (NEPSE closed)

    const trend = (days - i) / days * 0.15;
    const noise = (random() - 0.48) * volatility * 2;
    const dayReturn = trend / days + noise;

    basePrice = basePrice * (1 + dayReturn);
    const dayHigh = basePrice * (1 + random() * volatility);
    const dayLow = basePrice * (1 - random() * volatility);
    const dayOpen = dayLow + random() * (dayHigh - dayLow);
    const dayClose = dayLow + random() * (dayHigh - dayLow);
    const dayVolume = Math.round(stock.avgVolume20d * (0.6 + random() * 0.9));

    data.push({
      date: date.toISOString().split('T')[0],
      open: Math.round(dayOpen * 100) / 100,
      high: Math.round(dayHigh * 100) / 100,
      low: Math.round(dayLow * 100) / 100,
      close: Math.round(dayClose * 100) / 100,
      volume: dayVolume,
    });
  }

  if (data.length > 0) {
    data[data.length - 1].close = stock.cmp;
  }

  return data;
}
