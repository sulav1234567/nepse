"""
NEPSE-ALPHA ULTIMATE — Demo Data
Realistic NEPSE stock data for development and offline mode.
"""

import numpy as np
from datetime import datetime, timedelta
from .models import StockData, HistoricalPrice, MarketOverview, SectorPerformance


DEMO_STOCKS = [
    StockData(symbol="NABIL", name="Nabil Bank Limited", sector="Commercial Bank",
        cmp=1285, previous_close=1270, change=15, change_percent=1.18,
        volume=45230, avg_volume_20d=38000, high_52w=1450, low_52w=980,
        eps=42.5, pe=30.2, pb=2.8, roe=16.2, dividend_yield=3.5, book_value=459, market_cap=98500000000),
    StockData(symbol="NICA", name="NIC Asia Bank Limited", sector="Commercial Bank",
        cmp=845, previous_close=838, change=7, change_percent=0.84,
        volume=125600, avg_volume_20d=95000, high_52w=1020, low_52w=620,
        eps=28.3, pe=29.9, pb=2.1, roe=14.8, dividend_yield=4.2, book_value=402, market_cap=72300000000),
    StockData(symbol="GBIME", name="Global IME Bank Limited", sector="Commercial Bank",
        cmp=362, previous_close=356, change=6, change_percent=1.69,
        volume=189340, avg_volume_20d=145000, high_52w=428, low_52w=265,
        eps=18.7, pe=19.4, pb=1.4, roe=13.5, dividend_yield=5.8, book_value=259, market_cap=56800000000),
    StockData(symbol="ADBL", name="Agriculture Development Bank", sector="Commercial Bank",
        cmp=498, previous_close=510, change=-12, change_percent=-2.35,
        volume=67800, avg_volume_20d=55000, high_52w=620, low_52w=380,
        eps=22.1, pe=22.5, pb=1.6, roe=12.8, dividend_yield=6.1, book_value=311, market_cap=42100000000),
    StockData(symbol="HBL", name="Himalayan Bank Limited", sector="Commercial Bank",
        cmp=572, previous_close=565, change=7, change_percent=1.24,
        volume=34560, avg_volume_20d=42000, high_52w=680, low_52w=420,
        eps=25.8, pe=22.2, pb=1.7, roe=14.1, dividend_yield=4.8, book_value=336, market_cap=38900000000),
    StockData(symbol="SCB", name="Standard Chartered Bank Nepal", sector="Commercial Bank",
        cmp=892, previous_close=875, change=17, change_percent=1.94,
        volume=12340, avg_volume_20d=15000, high_52w=1050, low_52w=710,
        eps=38.2, pe=23.4, pb=3.2, roe=18.5, dividend_yield=3.1, book_value=279, market_cap=28500000000),
    StockData(symbol="PRVU", name="Prabhu Bank Limited", sector="Commercial Bank",
        cmp=318, previous_close=322, change=-4, change_percent=-1.24,
        volume=98700, avg_volume_20d=82000, high_52w=395, low_52w=235,
        eps=15.2, pe=20.9, pb=1.2, roe=11.8, dividend_yield=5.5, book_value=265, market_cap=35200000000),
    StockData(symbol="SBL", name="Siddhartha Bank Limited", sector="Commercial Bank",
        cmp=410, previous_close=405, change=5, change_percent=1.23,
        volume=78900, avg_volume_20d=65000, high_52w=498, low_52w=310,
        eps=20.5, pe=20.0, pb=1.5, roe=13.2, dividend_yield=5.2, book_value=273, market_cap=44600000000),
    StockData(symbol="MNBBL", name="Muktinath Bikas Bank", sector="Development Bank",
        cmp=485, previous_close=472, change=13, change_percent=2.75,
        volume=56780, avg_volume_20d=35000, high_52w=558, low_52w=345,
        eps=24.6, pe=19.7, pb=1.8, roe=15.2, dividend_yield=4.1, book_value=269, market_cap=18200000000),
    StockData(symbol="SINDU", name="Sindhu Bikash Bank", sector="Development Bank",
        cmp=342, previous_close=348, change=-6, change_percent=-1.72,
        volume=23400, avg_volume_20d=18000, high_52w=412, low_52w=260,
        eps=16.8, pe=20.4, pb=1.3, roe=12.5, dividend_yield=4.8, book_value=263, market_cap=8500000000),
    StockData(symbol="NHPC", name="Nepal Hydro Developers Ltd", sector="Hydropower",
        cmp=655, previous_close=625, change=30, change_percent=4.80,
        volume=142300, avg_volume_20d=68000, high_52w=720, low_52w=380,
        eps=12.8, pe=51.2, pb=4.5, roe=9.2, dividend_yield=1.5, book_value=146, market_cap=12400000000),
    StockData(symbol="UPPER", name="Upper Tamakoshi Hydropower", sector="Hydropower",
        cmp=520, previous_close=505, change=15, change_percent=2.97,
        volume=235600, avg_volume_20d=180000, high_52w=608, low_52w=320,
        eps=8.5, pe=61.2, pb=3.8, roe=7.8, dividend_yield=1.0, book_value=137, market_cap=45600000000),
    StockData(symbol="BPCL", name="Butwal Power Company", sector="Hydropower",
        cmp=438, previous_close=442, change=-4, change_percent=-0.90,
        volume=34500, avg_volume_20d=28000, high_52w=530, low_52w=350,
        eps=18.2, pe=24.1, pb=2.2, roe=10.5, dividend_yield=3.2, book_value=199, market_cap=15800000000),
    StockData(symbol="RADHI", name="Radhi Bidyut Company Limited", sector="Hydropower",
        cmp=590, previous_close=575, change=15, change_percent=2.61,
        volume=18700, avg_volume_20d=12000, high_52w=680, low_52w=410,
        eps=22.5, pe=26.2, pb=2.8, roe=11.2, dividend_yield=2.8, book_value=211, market_cap=8900000000),
    StockData(symbol="NLIC", name="Nepal Life Insurance Company", sector="Insurance",
        cmp=1225, previous_close=1210, change=15, change_percent=1.24,
        volume=28900, avg_volume_20d=22000, high_52w=1480, low_52w=890,
        eps=52.3, pe=23.4, pb=4.2, roe=22.5, dividend_yield=2.2, book_value=292, market_cap=35600000000),
    StockData(symbol="SICL", name="Shikhar Insurance Company", sector="Insurance",
        cmp=820, previous_close=812, change=8, change_percent=0.99,
        volume=15600, avg_volume_20d=12000, high_52w=980, low_52w=620,
        eps=35.8, pe=22.9, pb=3.5, roe=18.2, dividend_yield=3.0, book_value=234, market_cap=12300000000),
    StockData(symbol="CBBL", name="Chhimek Laghubitta Bikas Bank", sector="Microfinance",
        cmp=1680, previous_close=1650, change=30, change_percent=1.82,
        volume=8900, avg_volume_20d=6500, high_52w=2050, low_52w=1280,
        eps=68.5, pe=24.5, pb=3.8, roe=19.5, dividend_yield=2.5, book_value=442, market_cap=9800000000),
    StockData(symbol="NMBMF", name="NMB Microfinance Bittiya Sanstha", sector="Microfinance",
        cmp=2450, previous_close=2420, change=30, change_percent=1.24,
        volume=4500, avg_volume_20d=3800, high_52w=2980, low_52w=1850,
        eps=82.3, pe=29.8, pb=4.5, roe=21.2, dividend_yield=1.8, book_value=544, market_cap=7200000000),
    StockData(symbol="UNL", name="Unilever Nepal Limited", sector="Manufacturing",
        cmp=15200, previous_close=15100, change=100, change_percent=0.66,
        volume=1200, avg_volume_20d=950, high_52w=18500, low_52w=12000,
        eps=520, pe=29.2, pb=28.5, roe=85.2, dividend_yield=3.4, book_value=533, market_cap=11400000000),
    StockData(symbol="SHL", name="Soaltee Hotel Limited", sector="Hotel & Tourism",
        cmp=468, previous_close=455, change=13, change_percent=2.86,
        volume=42300, avg_volume_20d=25000, high_52w=545, low_52w=320,
        eps=8.5, pe=55.1, pb=2.1, roe=6.2, dividend_yield=0.8, book_value=223, market_cap=6500000000),
]


def generate_historical_prices(stock: StockData, days: int = 60) -> list[HistoricalPrice]:
    """Generate realistic historical OHLCV data for a stock."""
    rng = np.random.default_rng(hash(stock.symbol) % (2**32))
    data = []
    base_price = stock.cmp * 0.85

    volatility_map = {
        "Hydropower": 0.035, "Commercial Bank": 0.018,
        "Development Bank": 0.022, "Insurance": 0.022,
        "Microfinance": 0.028, "Manufacturing": 0.015,
        "Hotel & Tourism": 0.030,
    }
    volatility = volatility_map.get(stock.sector, 0.025)

    now = datetime.now()
    for i in range(days, 0, -1):
        date = now - timedelta(days=i)
        if date.weekday() == 5:  # Skip Saturday (NEPSE closed)
            continue

        trend = (days - i) / days * 0.15
        noise = (rng.random() - 0.48) * volatility * 2
        day_return = trend / days + noise
        base_price *= (1 + day_return)

        high = base_price * (1 + rng.random() * volatility)
        low = base_price * (1 - rng.random() * volatility)
        open_p = low + rng.random() * (high - low)
        close_p = low + rng.random() * (high - low)
        volume = int(stock.avg_volume_20d * (0.6 + rng.random() * 0.9))

        data.append(HistoricalPrice(
            date=date.strftime("%Y-%m-%d"),
            open=round(open_p, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_p, 2),
            volume=volume,
        ))

    if data:
        data[-1].close = stock.cmp
    return data


DEMO_MARKET = MarketOverview(
    nepse_index=2845.67, nepse_change=32.45, nepse_change_percent=1.15,
    total_turnover=8456000000, total_volume=12345678, total_transactions=45678,
    advancers=142, decliners=78, unchanged=15,
    regime="BULL TREND", regime_confidence=72,
    interbank_rate=4.25, t_bill_yield=5.8,
)

DEMO_SECTORS = [
    SectorPerformance(sector="Commercial Bank", index=2156.3, change=28.4, change_percent=1.33, volume=4560000),
    SectorPerformance(sector="Development Bank", index=3845.2, change=42.1, change_percent=1.11, volume=1230000),
    SectorPerformance(sector="Hydropower", index=2890.8, change=85.6, change_percent=3.05, volume=3210000),
    SectorPerformance(sector="Insurance", index=9425.1, change=48.2, change_percent=0.51, volume=890000),
    SectorPerformance(sector="Microfinance", index=4215.6, change=62.3, change_percent=1.50, volume=560000),
    SectorPerformance(sector="Manufacturing", index=5102.4, change=12.1, change_percent=0.24, volume=120000),
    SectorPerformance(sector="Hotel & Tourism", index=2456.8, change=78.9, change_percent=3.32, volume=340000),
    SectorPerformance(sector="Finance", index=1892.5, change=-15.3, change_percent=-0.80, volume=780000),
    SectorPerformance(sector="Trading", index=2145.0, change=5.2, change_percent=0.24, volume=210000),
    SectorPerformance(sector="Others", index=1567.3, change=-8.4, change_percent=-0.53, volume=150000),
]
