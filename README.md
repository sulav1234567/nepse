# NEPSE-ALPHA ULTIMATE

> Five-Layer Stock Prediction Intelligence for Nepal Stock Exchange

![NEPSE Dashboard](https://github.com/user-attachments/assets/9eabb967-ff10-481c-a7bd-87991951421b)

## 🚀 Quick Start - View the Application

### Option 1: Quick Start (2 commands)

**Terminal 1 - Backend:**
```bash
pip install -q fastapi uvicorn httpx pydantic numpy pandas scipy scikit-learn statsmodels filterpy xgboost beautifulsoup4 lxml aiohttp joblib
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
npm install
npm run dev
```

**View:** Open http://localhost:3000 in your browser 🎉

### Option 2: Detailed Setup

See [SETUP.md](SETUP.md) for complete instructions.

## ✨ What You'll See

The NEPSE-ALPHA dashboard provides:

- **📊 Real-Time Market Overview** - NEPSE Index, Turnover, Market Breadth
- **🎯 Top 5 Stock Picks** - Daily signals with FCS (Five-layer Composite Score)
- **📈 Sector Performance** - Visual charts of all sectors
- **🔬 Five-Layer Analysis** - FVL, TML, SSIL, GTBIL, MRLLL scoring
- **🤖 AI Predictions** - ML-powered stock predictions
- **💼 Portfolio Optimizer** - Sortino ratio-based allocation
- **🧠 Autonomous Intelligence** - Always-on ensemble research dashboard at `/autonomous`

## 🏗️ Architecture

This is a [Next.js](https://nextjs.org) project with a FastAPI backend:

```
Frontend (Next.js + React) → Backend (FastAPI) → NEPSE API (live data)
                                                ↓
                                          Demo Data (fallback)
```

The repo also includes an autonomous research subsystem with Timescale-ready storage, Celery workers, and an ensemble modeling pipeline.

- Architecture doc: [docs/autonomous-architecture.md](/Users/sulavkhatiwada/Desktop/nepse-main/docs/autonomous-architecture.md)
- Docker stack: [docker-compose.yml](/Users/sulavkhatiwada/Desktop/nepse-main/docker-compose.yml)

## 📱 Features

- **Real-time Data**: Fetches live data from NEPSE official API
- **Graceful Fallback**: Uses demo data when API unavailable
- **Five-Layer Scoring**: Advanced stock analysis framework
- **ML Predictions**: Ensemble models (RandomForest, XGBoost, GradientBoosting)
- **Regime Detection**: Adapts strategy based on market conditions
- **Portfolio Optimization**: Risk-adjusted allocation with Sortino ratio

## 🛠️ Tech Stack

- **Frontend**: Next.js 16, React 19, TypeScript, Recharts
- **Backend**: FastAPI, Python 3.12
- **Analysis**: NumPy, Pandas, SciPy, Scikit-learn, Statsmodels
- **ML**: XGBoost, RandomForest, GradientBoosting
- **Data**: Live NEPSE API + Demo fallback

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Detailed setup guide
- **[COLAB_CONTINUOUS_TRAINING.md](COLAB_CONTINUOUS_TRAINING.md)** - Train the model on Google Colab
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment

## 🔗 API Endpoints

Once the backend is running, explore:

- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/api/health
- **Stocks List**: http://localhost:8000/api/stocks
- **Market Data**: http://localhost:8000/api/market
- **AI Predictions**: http://localhost:8000/api/ai/predictions

## 🧪 Data Mode

Check what data you're seeing:
```bash
curl http://localhost:8000/api/health | jq .data_mode
```

Returns:
- `"LIVE API (fallback: DEMO) - Current: LIVE"` - Using real NEPSE data
- `"LIVE API (fallback: DEMO) - Current: DEMO"` - Using demo data (20 realistic stocks)

## 📖 Learn More

## 📝 License

This project is licensed under the terms specified in the repository.

## 🤝 Contributing

## 🚢 Deploy on Vercel

## 📞 Support

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

See LICENSE file for details.

---

**Built with ❤️ for NEPSE traders and investors**
