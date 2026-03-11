# NEPSE-ALPHA Setup Guide

## Overview

NEPSE-ALPHA is a stock prediction and analysis platform for the Nepal Stock Exchange (NEPSE). It consists of:

- **Backend**: FastAPI server with real-time data fetching and ML predictions
- **Frontend**: Next.js application for visualization and interaction

## Architecture

```
Frontend (Next.js) → Backend API (FastAPI) → NEPSE API (live data)
                                           ↓
                                    Demo Data (fallback)
```

## Backend Setup

### Prerequisites

- Python 3.8+ (tested with Python 3.12)
- pip package manager

### Installation

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Note: `pypfopt` is not compatible with Python 3.12+. The portfolio optimization will use a fallback implementation if pypfopt is not available.

### Running the Backend

Start the FastAPI server:

```bash
cd /path/to/nepse
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

- `GET /api/health` - Check API status and data source (LIVE or DEMO)
- `GET /api/market` - Market overview with NEPSE index
- `GET /api/stocks` - All stocks with FCS analysis
- `GET /api/stocks/{symbol}` - Detailed analysis for a stock
- `GET /api/predictions/daily` - Top 5 daily predictions
- `GET /api/predictions/weekly` - Top 10 weekly predictions
- `GET /api/predictions/monthly` - Top 5 monthly predictions
- `GET /api/portfolio` - Optimized portfolio allocation
- `GET /api/ai/predictions` - ML-powered predictions

## Frontend Setup

### Prerequisites

- Node.js 18+ and npm

### Installation

1. Navigate to the project root:
```bash
cd /path/to/nepse
```

2. Install dependencies:
```bash
npm install
```

### Configuration

Set the backend API URL (optional, defaults to `http://localhost:8000`):

```bash
export NEXT_PUBLIC_API_URL=http://localhost:8000
```

Or create a `.env.local` file:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Running the Frontend

```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### Building for Production

```bash
npm run build
npm start
```

## Data Sources

The application uses a hybrid data approach:

1. **LIVE Mode**: Fetches real-time data from NEPSE official API (`https://nepalstock.com.np`)
2. **DEMO Mode**: Falls back to realistic demo data when NEPSE API is unavailable

Check the current mode via:
```bash
curl http://localhost:8000/api/health
```

Response includes:
```json
{
  "status": "operational",
  "data_mode": "LIVE API (fallback: DEMO) - Current: LIVE",
  "stocks_loaded": 250
}
```

## Features

### Five-Layer Analysis (FCS)
1. **FVL** (Fundamental Valuation Layer) - PE, PB, ROE, Dividend Yield
2. **TML** (Technical Momentum Layer) - RSI, MACD, Moving Averages
3. **SSIL** (Supply-Side Intelligence Layer) - Volume analysis
4. **GTBIL** (Go-To-Bed-In-Love Layer) - Risk assessment
5. **MRLLL** (Market Regime Learning Layer) - Market context

### ML Predictions
- Ensemble of RandomForest, GradientBoosting, and XGBoost
- 30+ engineered features
- Probability-based ranking

### Portfolio Optimization
- Sortino ratio optimization
- Regime-based position sizing
- Risk-adjusted allocation

## Troubleshooting

### Backend Issues

**Problem**: SSL certificate errors
```
Solution: The app removes SSL verification bypass. If you encounter SSL errors, 
verify your network connection or temporarily add verify=False in nepse_fetcher.py 
(not recommended for production).
```

**Problem**: NEPSE API authentication fails
```
Solution: The API uses "Salter" authorization header. If this fails, check 
NEPSE API documentation for the correct authentication scheme.
```

### Frontend Issues

**Problem**: Cannot connect to backend
```
Solution: Ensure backend is running on port 8000 and NEXT_PUBLIC_API_URL is correct.
```

**Problem**: CORS errors
```
Solution: Backend allows all origins by default. Check FastAPI CORS middleware 
configuration if issues persist.
```

## Development

### Backend Development

- Main server: `backend/server.py`
- Data fetching: `backend/nepse_fetcher.py`
- Analysis engine: `backend/engine.py`
- ML models: `backend/ml_predictor.py`
- Models: `backend/models.py`

### Frontend Development

- Main dashboard: `src/app/page.tsx`
- API client: `src/lib/api-client.ts`
- Components: `src/components/`

## Performance

- Backend caches API responses for 60 seconds
- Historical data is generated on-demand
- ML models train once and cache predictions

## Security Notes

- SSL verification is enabled (production-ready)
- CORS allows all origins (configure for production)
- No authentication required (add for production use)

## Contributing

1. Fix bugs in backend (nepse_fetcher.py, server.py)
2. Add frontend pages to use API client
3. Implement real-time updates via WebSocket
4. Add user authentication
5. Deploy to production

## License

See LICENSE file for details.
