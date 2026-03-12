# NEPSE-ALPHA ULTIMATE

**Five-Layer Stock Prediction Intelligence System for Nepal Stock Exchange**

A sophisticated full-stack application combining advanced technical analysis, machine learning predictions, and portfolio optimization for NEPSE stocks.

## 🌟 Features

- **Real-time NEPSE Data Integration** - Live stock prices and market data from NEPSE official API
- **Five-Layer Analysis Engine** - Comprehensive stock analysis combining:
  - FVL (Fundamental Value Layer)
  - TML (Technical Momentum Layer)
  - SSIL (Social Sentiment Intelligence Layer)
  - GTBIL (Guru-Trader Behavioral Intelligence Layer)
  - MRLLL (Macro-Regime Lead-Lag Layer)
- **AI/ML Predictions** - Ensemble machine learning (RandomForest + XGBoost + GradientBoosting)
- **Multi-timeframe Signals** - Daily, Weekly, and Monthly trading predictions
- **Portfolio Optimization** - Sortino ratio-based allocation with regime constraints
- **Stock Screener** - Advanced filtering by sector, FCS scores, and technical metrics
- **Automatic Fallback** - Seamlessly switches to demo data when live API is unavailable

## 🚀 Quick Start

### Prerequisites
- Node.js 20+ and npm
- Python 3.10+ and pip

### One-Command Start
```bash
chmod +x start.sh
./start.sh
```

This will:
1. Install all dependencies (first time only)
2. Start the backend API server (port 8000)
3. Start the frontend development server (port 3000)

Access the application at **http://localhost:3000**

### Manual Setup

**1. Install Dependencies**

Frontend:
```bash
npm install
```

Backend:
```bash
cd backend
pip install -r requirements.txt
cd ..
```

**2. Start Backend Server**
```bash
cd backend
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

**3. Start Frontend** (in a new terminal)
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## 📊 Application Pages

- **Dashboard** - Market overview, top 5 daily signals, sector performance
- **Stock Screener** - Filter and sort all NEPSE stocks by various metrics
- **Predictions** - Daily/Weekly/Monthly trading signals with classification
- **AI Predictions** - ML-powered stock rise predictions with feature importance
- **Deep Analysis** - Comprehensive five-layer analysis for individual stocks
- **Portfolio Optimizer** - Optimal allocation based on FCS scores and Sortino ratio
- **Self-Audit** - Backtest and track prediction performance

## 💾 Data Sources

The application intelligently manages data sources:

- **🟢 LIVE DATA** - Real-time data from NEPSE official API (when available)
- **🟡 DEMO DATA** - High-quality demo data (automatic fallback)

Each page displays a badge indicating the current data source. The system automatically falls back to demo data if:
- Backend server is not running
- NEPSE API is unavailable
- Network connectivity issues

## 🏗️ Architecture

```
Frontend (Next.js + React)  →  Backend (FastAPI + Python)  →  NEPSE API
         ↓ (fallback)
    Demo Data (built-in)
```

## 📚 Documentation

- [DEPLOYMENT.md](./DEPLOYMENT.md) - Complete deployment and configuration guide
- API Documentation - http://localhost:8000/docs (when backend is running)

## 🛠️ Technology Stack

**Frontend:**
- Next.js 16 with React 19
- TypeScript
- Recharts for data visualization
- Lucide React for icons

**Backend:**
- FastAPI (Python web framework)
- NumPy, Pandas, SciPy (numerical computing)
- Scikit-learn, XGBoost (machine learning)
- Statsmodels, Filterpy (statistical analysis)
- HTTPX (async HTTP for NEPSE API)

## 🔧 Development

### Build for Production
```bash
npm run build
npm run start
```

### Lint Code
```bash
npm run lint
```

### Environment Variables

Create `.env.local` in the root directory:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production, set this to your backend API URL.

## 📖 API Endpoints

Key endpoints (when backend is running):

- `GET /api/live/stocks` - Real-time stock data
- `GET /api/live/market` - Live market overview
- `GET /api/predictions/daily` - Top 5 daily signals
- `GET /api/ai/predictions` - ML predictions
- `GET /api/portfolio` - Optimized portfolio

Full API documentation: http://localhost:8000/docs

## 🐛 Troubleshooting

**Issue**: Data badge shows "DEMO DATA" even when backend is running

**Solution**: 
1. Verify backend is accessible: `curl http://localhost:8000/api/health`
2. Check NEXT_PUBLIC_API_URL in `.env.local`
3. Ensure no CORS errors in browser console

**Issue**: Backend fails to start

**Solution**:
1. Check Python version: `python3 --version` (needs 3.10+)
2. Install system dependencies (Ubuntu): `sudo apt-get install python3-dev build-essential`
3. Check logs for missing packages

See [DEPLOYMENT.md](./DEPLOYMENT.md) for more troubleshooting.

## 📝 License

This project is licensed under the terms specified in the repository.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues and questions:
- GitHub Issues: https://github.com/sulav1234567/nepse/issues
