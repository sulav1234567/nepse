// ============================================================================
// NEPSE-ALPHA ULTIMATE — Demo Data
// Realistic NEPSE stock data for development and offline mode
// ============================================================================

import { Stock, HistoricalPrice, MarketOverview, SectorPerformance } from './types';

export const DEMO_STOCKS: Stock[] = [
  // Commercial Banks
  {
    symbol: 'NABIL', name: 'Nabil Bank Limited', sector: 'Commercial Bank',
    cmp: 1285, previousClose: 1270, change: 15, changePercent: 1.18,
    volume: 45230, avgVolume20d: 38000, high52w: 1450, low52w: 980,
    eps: 42.5, pe: 30.2, pb: 2.8, roe: 16.2, dividendYield: 3.5, bookValue: 459, marketCap: 98500000000
  },
  {
    symbol: 'NICA', name: 'NIC Asia Bank Limited', sector: 'Commercial Bank',
    cmp: 845, previousClose: 838, change: 7, changePercent: 0.84,
    volume: 125600, avgVolume20d: 95000, high52w: 1020, low52w: 620,
    eps: 28.3, pe: 29.9, pb: 2.1, roe: 14.8, dividendYield: 4.2, bookValue: 402, marketCap: 72300000000
  },
  {
    symbol: 'GBIME', name: 'Global IME Bank Limited', sector: 'Commercial Bank',
    cmp: 362, previousClose: 356, change: 6, changePercent: 1.69,
    volume: 189340, avgVolume20d: 145000, high52w: 428, low52w: 265,
    eps: 18.7, pe: 19.4, pb: 1.4, roe: 13.5, dividendYield: 5.8, bookValue: 259, marketCap: 56800000000
  },
  {
    symbol: 'ADBL', name: 'Agriculture Development Bank', sector: 'Commercial Bank',
    cmp: 498, previousClose: 510, change: -12, changePercent: -2.35,
    volume: 67800, avgVolume20d: 55000, high52w: 620, low52w: 380,
    eps: 22.1, pe: 22.5, pb: 1.6, roe: 12.8, dividendYield: 6.1, bookValue: 311, marketCap: 42100000000
  },
  {
    symbol: 'HBL', name: 'Himalayan Bank Limited', sector: 'Commercial Bank',
    cmp: 572, previousClose: 565, change: 7, changePercent: 1.24,
    volume: 34560, avgVolume20d: 42000, high52w: 680, low52w: 420,
    eps: 25.8, pe: 22.2, pb: 1.7, roe: 14.1, dividendYield: 4.8, bookValue: 336, marketCap: 38900000000
  },
  {
    symbol: 'SCB', name: 'Standard Chartered Bank Nepal', sector: 'Commercial Bank',
    cmp: 892, previousClose: 875, change: 17, changePercent: 1.94,
    volume: 12340, avgVolume20d: 15000, high52w: 1050, low52w: 710,
    eps: 38.2, pe: 23.4, pb: 3.2, roe: 18.5, dividendYield: 3.1, bookValue: 279, marketCap: 28500000000
  },
  {
    symbol: 'PRVU', name: 'Prabhu Bank Limited', sector: 'Commercial Bank',
    cmp: 318, previousClose: 322, change: -4, changePercent: -1.24,
    volume: 98700, avgVolume20d: 82000, high52w: 395, low52w: 235,
    eps: 15.2, pe: 20.9, pb: 1.2, roe: 11.8, dividendYield: 5.5, bookValue: 265, marketCap: 35200000000
  },
  {
    symbol: 'SBL', name: 'Siddhartha Bank Limited', sector: 'Commercial Bank',
    cmp: 410, previousClose: 405, change: 5, changePercent: 1.23,
    volume: 78900, avgVolume20d: 65000, high52w: 498, low52w: 310,
    eps: 20.5, pe: 20.0, pb: 1.5, roe: 13.2, dividendYield: 5.2, bookValue: 273, marketCap: 44600000000
  },
  // Development Banks
  {
    symbol: 'MNBBL', name: 'Muktinath Bikas Bank', sector: 'Development Bank',
    cmp: 485, previousClose: 472, change: 13, changePercent: 2.75,
    volume: 56780, avgVolume20d: 35000, high52w: 558, low52w: 345,
    eps: 24.6, pe: 19.7, pb: 1.8, roe: 15.2, dividendYield: 4.1, bookValue: 269, marketCap: 18200000000
  },
  {
    symbol: 'SINDU', name: 'Sindhu Bikash Bank', sector: 'Development Bank',
    cmp: 342, previousClose: 348, change: -6, changePercent: -1.72,
    volume: 23400, avgVolume20d: 18000, high52w: 412, low52w: 260,
    eps: 16.8, pe: 20.4, pb: 1.3, roe: 12.5, dividendYield: 4.8, bookValue: 263, marketCap: 8500000000
  },
  // Hydropower
  {
    symbol: 'NHPC', name: 'Nepal Hydro Developers Ltd', sector: 'Hydropower',
    cmp: 655, previousClose: 625, change: 30, changePercent: 4.80,
    volume: 142300, avgVolume20d: 68000, high52w: 720, low52w: 380,
    eps: 12.8, pe: 51.2, pb: 4.5, roe: 9.2, dividendYield: 1.5, bookValue: 146, marketCap: 12400000000
  },
  {
    symbol: 'UPPER', name: 'Upper Tamakoshi Hydropower', sector: 'Hydropower',
    cmp: 520, previousClose: 505, change: 15, changePercent: 2.97,
    volume: 235600, avgVolume20d: 180000, high52w: 608, low52w: 320,
    eps: 8.5, pe: 61.2, pb: 3.8, roe: 7.8, dividendYield: 1.0, bookValue: 137, marketCap: 45600000000
  },
  {
    symbol: 'BPCL', name: 'Butwal Power Company', sector: 'Hydropower',
    cmp: 438, previousClose: 442, change: -4, changePercent: -0.90,
    volume: 34500, avgVolume20d: 28000, high52w: 530, low52w: 350,
    eps: 18.2, pe: 24.1, pb: 2.2, roe: 10.5, dividendYield: 3.2, bookValue: 199, marketCap: 15800000000
  },
  {
    symbol: 'RADHI', name: 'Radhi Bidyut Company Limited', sector: 'Hydropower',
    cmp: 590, previousClose: 575, change: 15, changePercent: 2.61,
    volume: 18700, avgVolume20d: 12000, high52w: 680, low52w: 410,
    eps: 22.5, pe: 26.2, pb: 2.8, roe: 11.2, dividendYield: 2.8, bookValue: 211, marketCap: 8900000000
  },
  // Insurance
  {
    symbol: 'NLIC', name: 'Nepal Life Insurance Company', sector: 'Insurance',
    cmp: 1225, previousClose: 1210, change: 15, changePercent: 1.24,
    volume: 28900, avgVolume20d: 22000, high52w: 1480, low52w: 890,
    eps: 52.3, pe: 23.4, pb: 4.2, roe: 22.5, dividendYield: 2.2, bookValue: 292, marketCap: 35600000000
  },
  {
    symbol: 'SICL', name: 'Shikhar Insurance Company', sector: 'Insurance',
    cmp: 820, previousClose: 812, change: 8, changePercent: 0.99,
    volume: 15600, avgVolume20d: 12000, high52w: 980, low52w: 620,
    eps: 35.8, pe: 22.9, pb: 3.5, roe: 18.2, dividendYield: 3.0, bookValue: 234, marketCap: 12300000000
  },
  // Microfinance
  {
    symbol: 'CBBL', name: 'Chhimek Laghubitta Bikas Bank', sector: 'Microfinance',
    cmp: 1680, previousClose: 1650, change: 30, changePercent: 1.82,
    volume: 8900, avgVolume20d: 6500, high52w: 2050, low52w: 1280,
    eps: 68.5, pe: 24.5, pb: 3.8, roe: 19.5, dividendYield: 2.5, bookValue: 442, marketCap: 9800000000
  },
  {
    symbol: 'NMBMF', name: 'NMB Microfinance Bittiya Sanstha', sector: 'Microfinance',
    cmp: 2450, previousClose: 2420, change: 30, changePercent: 1.24,
    volume: 4500, avgVolume20d: 3800, high52w: 2980, low52w: 1850,
    eps: 82.3, pe: 29.8, pb: 4.5, roe: 21.2, dividendYield: 1.8, bookValue: 544, marketCap: 7200000000
  },
  // Manufacturing & Hotel
  {
    symbol: 'UNL', name: 'Unilever Nepal Limited', sector: 'Manufacturing',
    cmp: 15200, previousClose: 15100, change: 100, changePercent: 0.66,
    volume: 1200, avgVolume20d: 950, high52w: 18500, low52w: 12000,
    eps: 520, pe: 29.2, pb: 28.5, roe: 85.2, dividendYield: 3.4, bookValue: 533, marketCap: 11400000000
  },
  {
    symbol: 'SHL', name: 'Soaltee Hotel Limited', sector: 'Hotel & Tourism',
    cmp: 468, previousClose: 455, change: 13, changePercent: 2.86,
    volume: 42300, avgVolume20d: 25000, high52w: 545, low52w: 320,
    eps: 8.5, pe: 55.1, pb: 2.1, roe: 6.2, dividendYield: 0.8, bookValue: 223, marketCap: 6500000000
  },
];

// Generate 60 days of historical data for a stock
export function generateHistoricalPrices(stock: Stock): HistoricalPrice[] {
  const data: HistoricalPrice[] = [];
  let basePrice = stock.cmp * 0.85; // Start ~15% below current price for uptrend effect
  const volatility = stock.sector === 'Hydropower' ? 0.035 : 
                     stock.sector === 'Commercial Bank' ? 0.018 :
                     stock.sector === 'Insurance' ? 0.022 : 0.025;
  
  const now = new Date();
  for (let i = 59; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    // Skip weekends (NEPSE is closed Sat-Sun actually trades Sun-Thu, but approximate)
    if (date.getDay() === 6) continue; // Skip Saturday
    
    const trend = (60 - i) / 60 * 0.15; // Gradual upward drift
    const noise = (Math.random() - 0.48) * volatility * 2;
    const dayReturn = trend / 60 + noise;
    
    basePrice = basePrice * (1 + dayReturn);
    const dayHigh = basePrice * (1 + Math.random() * volatility);
    const dayLow = basePrice * (1 - Math.random() * volatility);
    const dayOpen = dayLow + Math.random() * (dayHigh - dayLow);
    const dayClose = dayLow + Math.random() * (dayHigh - dayLow);
    const dayVolume = Math.round(stock.avgVolume20d * (0.6 + Math.random() * 0.9));
    
    data.push({
      date: date.toISOString().split('T')[0],
      open: Math.round(dayOpen * 100) / 100,
      high: Math.round(dayHigh * 100) / 100,
      low: Math.round(dayLow * 100) / 100,
      close: Math.round(dayClose * 100) / 100,
      volume: dayVolume,
    });
  }
  
  // Ensure the last close matches CMP
  if (data.length > 0) {
    data[data.length - 1].close = stock.cmp;
  }
  
  return data;
}

export const DEMO_MARKET_OVERVIEW: MarketOverview = {
  nepseIndex: 2845.67,
  nepseChange: 32.45,
  nepseChangePercent: 1.15,
  totalTurnover: 8456000000,
  totalVolume: 12345678,
  totalTransactions: 45678,
  advancers: 142,
  decliners: 78,
  unchanged: 15,
  regime: 'BULL TREND',
  regimeConfidence: 72,
  interbankRate: 4.25,
  tBillYield: 5.8,
};

export const DEMO_SECTOR_PERFORMANCE: SectorPerformance[] = [
  { sector: 'Commercial Bank', index: 2156.3, change: 28.4, changePercent: 1.33, volume: 4560000 },
  { sector: 'Development Bank', index: 3845.2, change: 42.1, changePercent: 1.11, volume: 1230000 },
  { sector: 'Hydropower', index: 2890.8, change: 85.6, changePercent: 3.05, volume: 3210000 },
  { sector: 'Insurance', index: 9425.1, change: 48.2, changePercent: 0.51, volume: 890000 },
  { sector: 'Microfinance', index: 4215.6, change: 62.3, changePercent: 1.50, volume: 560000 },
  { sector: 'Manufacturing', index: 5102.4, change: 12.1, changePercent: 0.24, volume: 120000 },
  { sector: 'Hotel & Tourism', index: 2456.8, change: 78.9, changePercent: 3.32, volume: 340000 },
  { sector: 'Finance', index: 1892.5, change: -15.3, changePercent: -0.80, volume: 780000 },
  { sector: 'Trading', index: 2145.0, change: 5.2, changePercent: 0.24, volume: 210000 },
  { sector: 'Others', index: 1567.3, change: -8.4, changePercent: -0.53, volume: 150000 },
];
