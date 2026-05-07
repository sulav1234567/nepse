# Quick Start Guide - How to View NEPSE-ALPHA

This guide will get you up and running in 5 minutes.

## Step 1: Start the Backend (Terminal 1)

```bash
cd /home/runner/work/nepse/nepse
pip install -q fastapi uvicorn httpx pydantic numpy pandas scipy scikit-learn statsmodels filterpy xgboost beautifulsoup4 lxml aiohttp joblib
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

**What you should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Test it:** Open http://localhost:8000/api/health in your browser

## Step 2: Start the Frontend (Terminal 2)

```bash
cd /home/runner/work/nepse/nepse
npm install
npm run dev
```

**What you should see:**
```
▲ Next.js 16.1.6
- Local:        http://localhost:3000
```

**View it:** Open http://localhost:3000 in your browser

## That's It! 🎉

You should now see the NEPSE-ALPHA dashboard with:
- Market Overview (NEPSE Index)
- Top Stock Picks with FCS Scores
- Sector Performance Charts
- Five-Layer Analysis Visualization

## Quick Reference

| Component | URL | Purpose |
|-----------|-----|---------|
| Frontend | http://localhost:3000 | Main Dashboard |
| Backend API | http://localhost:8000 | API Server |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Health Check | http://localhost:8000/api/health | Server Status |

## What Data Am I Seeing?

The application tries to fetch **live data** from NEPSE API. If unavailable, it falls back to **demo data** (20 realistic stocks).

Check the data source:
```bash
curl http://localhost:8000/api/health | jq .data_mode
# Returns: "LIVE API (fallback: DEMO) - Current: LIVE" or "...DEMO"
```

## Troubleshooting

### Backend won't start
```bash
# Make sure you're in the right directory
cd /home/runner/work/nepse/nepse

# Install dependencies
pip install -r backend/requirements.txt

# Try again
python -m uvicorn backend.server:app --port 8000
```

### Frontend won't start
```bash
# Make sure dependencies are installed
npm install

# Clear cache if needed
rm -rf .next
npm run dev
```

### Port already in use
```bash
# Backend on different port
python -m uvicorn backend.server:app --port 8001

# Update frontend API URL
export NEXT_PUBLIC_API_URL=http://localhost:8001
npm run dev
```

## Next Steps

- Explore the dashboard at http://localhost:3000
- Try different pages: Analysis, Predictions, AI Predictions, Portfolio
- Check API endpoints at http://localhost:8000/docs
- View detailed setup in [SETUP.md](SETUP.md)
