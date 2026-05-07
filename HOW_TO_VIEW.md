# How to View NEPSE-ALPHA - Complete Guide

## 🎯 What is NEPSE-ALPHA?

NEPSE-ALPHA is a sophisticated stock prediction and analysis platform for the Nepal Stock Exchange. It combines:
- **Five-Layer Analysis Framework** (FVL, TML, SSIL, GTBIL, MRLLL)
- **Machine Learning Predictions** (RandomForest, XGBoost, GradientBoosting)
- **Real-time NEPSE Data** with automatic fallback to demo data
- **Portfolio Optimization** using Sortino ratio
- **Market Regime Detection** for adaptive strategies

## 🚀 Quick Start (2 Commands)

### Terminal 1️⃣ - Start Backend

```bash
# Install dependencies (one-time)
pip install -q fastapi uvicorn httpx pydantic numpy pandas scipy scikit-learn statsmodels filterpy xgboost beautifulsoup4 lxml aiohttp joblib

# Start server
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Terminal 2️⃣ - Start Frontend

```bash
# Install dependencies (one-time)
npm install

# Start development server
npm run dev
```

**Expected output:**
```
▲ Next.js 16.1.6
- Local:        http://localhost:3000
```

### 3️⃣ View in Browser

Open **http://localhost:3000** 🎉

## 📸 What You'll See

### Main Dashboard
![Dashboard Screenshot](https://github.com/user-attachments/assets/9eabb967-ff10-481c-a7bd-87991951421b)

**Features:**
- ✅ NEPSE Index with 30-day trend chart
- ✅ Market Breadth (Advancers/Decliners)
- ✅ Top 5 Daily Stock Signals with FCS scores
- ✅ Sector Performance bar chart
- ✅ Five-Layer Weight Distribution
- ✅ Market Regime Detection (Bull/Bear/Sideways)

### AI Predictions Page
![AI Predictions Screenshot](https://github.com/user-attachments/assets/fac42532-3337-4d58-b374-6c7091257f8d)

**Features:**
- ✅ ML Model Accuracy: 73.2% (trained on 100 samples)
- ✅ Top stock predictions with rise probability
- ✅ Ensemble model scores visualization
- ✅ Feature importance ranking
- ✅ AI reasoning for each prediction
- ✅ Rise probability heatmap for all 20 stocks

## 🗺️ Application Structure

```
┌─────────────────────────────────────────────────────────┐
│                    NEPSE-ALPHA                          │
├─────────────────────────────────────────────────────────┤
│  Frontend (Next.js)      │  Backend (FastAPI)          │
│  http://localhost:3000   │  http://localhost:8000      │
│                          │                              │
│  Pages:                  │  Endpoints:                  │
│  • Dashboard (/)         │  • /api/health               │
│  • Stock Screener        │  • /api/market               │
│  • Predictions           │  • /api/stocks               │
│  • AI Predictions        │  • /api/predictions/*        │
│  • Deep Analysis         │  • /api/ai/predictions       │
│  • Portfolio Optimizer   │  • /api/portfolio            │
│  • Self-Audit            │  • /docs (Swagger UI)        │
└─────────────────────────────────────────────────────────┘
                            ↓
                    NEPSE Official API
                    (nepalstock.com.np)
                            ↓
                    Demo Data Fallback
                    (20 realistic stocks)
```

## 🎨 Available Pages

Navigate through the sidebar:

1. **Dashboard** - Overview of market and top picks
2. **Stock Screener** - Filter stocks by criteria
3. **Predictions** - Daily, weekly, monthly signals
4. **AI Predictions** - ML-powered stock predictions
5. **Deep Analysis** - Detailed five-layer breakdown
6. **Portfolio Optimizer** - Risk-adjusted allocation
7. **Self-Audit** - Performance tracking

## 🔗 Useful URLs

| Resource | URL | Description |
|----------|-----|-------------|
| **Dashboard** | http://localhost:3000 | Main application |
| **API Docs** | http://localhost:8000/docs | Interactive Swagger UI |
| **Health Check** | http://localhost:8000/api/health | Server status |
| **All Stocks** | http://localhost:8000/api/stocks | List with FCS scores |
| **Market Data** | http://localhost:8000/api/market | NEPSE index & regime |
| **AI Predictions** | http://localhost:8000/api/ai/predictions | ML predictions JSON |

## 🧪 Check Data Source

The application uses live NEPSE data when available, falling back to demo data:

```bash
curl http://localhost:8000/api/health | jq .data_mode
```

**Response:**
- `"LIVE API (fallback: DEMO) - Current: LIVE"` = Real NEPSE data ✅
- `"LIVE API (fallback: DEMO) - Current: DEMO"` = Demo data (20 stocks) 📊

## 🛠️ Troubleshooting

### Backend won't start

**Problem:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
pip install -r backend/requirements.txt
# Or install individually
pip install fastapi uvicorn httpx pydantic numpy pandas scipy scikit-learn
```

### Frontend won't start

**Problem:** `sh: next: command not found`

**Solution:**
```bash
npm install
npm run dev
```

### Port already in use

**Backend:**
```bash
# Use different port
python -m uvicorn backend.server:app --port 8001
```

**Frontend:**
```bash
# Update API URL
export NEXT_PUBLIC_API_URL=http://localhost:8001
npm run dev
```

### CORS errors

**Solution:** Backend CORS is configured to allow all origins. If issues persist, check browser console.

## 📊 Understanding the Data

### Five-Layer Composite Score (FCS)

Each stock gets a score from 0-100 based on:

1. **FVL (25%)** - Fundamental Valuation Layer
   - PE ratio, PB ratio, ROE, Dividend yield

2. **TML (25%)** - Technical Momentum Layer
   - RSI, MACD, Moving averages

3. **SSIL (15%)** - Supply-Side Intelligence Layer
   - Volume patterns, accumulation/distribution

4. **GTBIL (25%)** - Go-To-Bed-In-Love Layer
   - Risk assessment, quality metrics

5. **MRLLL (10%)** - Market Regime Learning Layer
   - Market context, regime adaptation

### Trading Signals

- **STRONG BUY** - FCS > 70
- **BUY** - FCS 60-70
- **SPECULATIVE BUY** - FCS 50-60
- **HOLD** - FCS 40-50
- **AVOID** - FCS 30-40
- **SHORT ALERT** - FCS < 30

### Market Regimes

- **BULL TREND** - Uptrend confirmed
- **BEAR TREND** - Downtrend confirmed
- **HIGH VOLATILITY** - Unstable conditions
- **SIDEWAYS** - Range-bound market
- **POLITICAL RISK** - Uncertain environment

## 🎓 Next Steps

1. **Explore the Dashboard** - Get familiar with the layout
2. **Check AI Predictions** - See ML model in action
3. **Try Stock Screener** - Filter stocks by your criteria
4. **View API Docs** - Explore http://localhost:8000/docs
5. **Read Documentation** - Check SETUP.md for details

## 📚 Additional Resources

- **QUICK_START.md** - This guide
- **SETUP.md** - Detailed setup instructions
- **BACKEND_FIXES_SUMMARY.md** - Technical changelog
- **API Documentation** - http://localhost:8000/docs

## 💡 Pro Tips

1. **Real-time Updates**: Frontend doesn't auto-refresh. Reload to see new data.
2. **Data Caching**: Backend caches API responses for 60 seconds.
3. **ML Training**: Models train on first request, subsequent calls are fast.
4. **Keyboard Shortcuts**: Use browser DevTools (F12) to inspect API calls.
5. **Mobile View**: Responsive design works on mobile browsers.

## 🆘 Getting Help

If you encounter issues:

1. Check backend logs in Terminal 1
2. Check frontend logs in Terminal 2
3. Check browser console (F12)
4. Review SETUP.md troubleshooting section
5. Verify both servers are running (check URLs)

## ✅ Verification Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] http://localhost:8000/api/health returns JSON
- [ ] http://localhost:3000 shows dashboard
- [ ] Sidebar navigation works
- [ ] Charts are visible
- [ ] Top 5 stocks are displayed

Once all checked, you're ready to analyze NEPSE stocks! 🎉

---

**Need more help?** Check SETUP.md or the technical documentation in BACKEND_FIXES_SUMMARY.md
