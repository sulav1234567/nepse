# 🚀 How to Run NEPSE-ALPHA

NEPSE-ALPHA is a real-time stock market intelligence system for Nepal Stock Exchange with real-time data fetching from NEPSE TMS.

## Quick Start (Recommended)

### 1️⃣ **Automated Setup & Run**
```bash
cd /Users/sulavkhatiwada/Desktop/nepse-main
chmod +x run.sh
./run.sh
```

This will:
- ✓ Check prerequisites (Python 3, Node.js)
- ✓ Create Python virtual environment if needed
- ✓ Install all dependencies
- ✓ Start backend API on `http://127.0.0.1:8000`
- ✓ Start frontend on `http://localhost:3000`

---

## Manual Step-by-Step

If you prefer manual control or the automated script doesn't work:

### Terminal 1 - Backend (FastAPI + NEPSE Real-Time Data)
```bash
cd /Users/sulavkhatiwada/Desktop/nepse-main

# Activate Python environment
source .venv/bin/activate

# Start backend API
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Terminal 2 - Frontend (Next.js Dashboard)
```bash
cd /Users/sulavkhatiwada/Desktop/nepse-main

# Start frontend
npm run dev
```

Expected output:
```
▲ Next.js 16.1.6
- Local:         http://localhost:3000
```

---

## 🎯 Access the Application

Once both servers are running:

| URL | Purpose |
|-----|---------|
| **http://localhost:3000** | Main Dashboard |
| **http://127.0.0.1:8000/api/health** | API Health Check |
| **http://127.0.0.1:8000/docs** | Interactive API Documentation |

---

## 📊 Real-Time Data Sources

NEPSE-ALPHA fetches real-time data from NEPSE TMS:

```
Priority Order:
1. NEPSE Official API (if available)
   └─ Falls back due to gzip response handling
   
2. Sharesansar (Primary - ALWAYS WORKS)
   └─ Provides: Stock prices, indices, market summary
   └─ Updates: Every 1-2 minutes
   
3. Merolagani (Backup)
   └─ Provides: Stock prices, indices
   └─ Updates: Hourly
```

✅ **Current Status**: Using Sharesansar real-time feeds (reliable, tested)

---

## 🔧 Environment Setup (First Time Only)

### Prerequisites
- Python 3.10+ ([install here](https://www.python.org/downloads/))
- Node.js 20+ ([install here](https://nodejs.org/))
- Git ([install here](https://git-scm.com/))

### Setup Steps
```bash
# Navigate to project
cd /Users/sulavkhatiwada/Desktop/nepse-main

# Create Python virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install Python dependencies
pip install -r backend/requirements.txt

# Install Node dependencies
npm ci

# You're ready to run!
```

---

## 🧪 Testing Data Fetching

Test if real-time NEPSE data is being fetched correctly:

```bash
source .venv/bin/activate
python test_nepse_api.py
```

This will show:
- ✓ Stock count fetched
- ✓ Market overview (NEPSE Index, change %)
- ✓ Top performers

---

## 🛠️ Troubleshooting

### Port Already in Use
If port 3000 or 8000 is busy:

```bash
# Find process using port 8000
lsof -i :8000
# Kill it
kill -9 <PID>

# Same for port 3000
lsof -i :3000
kill -9 <PID>
```

### Virtual Environment Issues
```bash
# Reinstall environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Node Dependencies Issues
```bash
rm -rf node_modules package-lock.json
npm ci
```

### SSL Certificate Issues
Already handled! The system:
- Disables SSL verification for NEPSE API (known certificate issue)
- Properly handles Sharesansar SSL
- Falls back gracefully

---

## 📋 Project Structure

```
nepse-main/
├── backend/                 # FastAPI + ML engines
│   ├── server.py           # Main API server
│   ├── nepse_fetcher.py    # Real-time data fetching
│   ├── engine.py           # Five-layer analysis
│   └── requirements.txt     # Python dependencies
├── src/                     # Next.js frontend
│   ├── app/
│   └── components/
├── run.sh                   # Automated run script
├── test_nepse_api.py       # Data fetching tests
├── package.json            # Node dependencies
└── tsconfig.json          # TypeScript config
```

---

## ✨ Features

- 📊 Real-time NEPSE index tracking
- 💹 Live stock prices (updated every 1-2 minutes)
- 📈 Technical analysis (RSI, MACD, EMA)
- 🎯 AI-powered stock predictions
- 📉 Sector performance analysis
- 🏆 Top performers & gainers
- 📱 Responsive dashboard

---

## 📞 Quick Commands Reference

```bash
# Start everything (recommended)
./run.sh

# Start backend only
source .venv/bin/activate && python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000

# Start frontend only
npm run dev

# Test data fetching
python test_nepse_api.py

# View API docs
open http://127.0.0.1:8000/docs

# View dashboard
open http://localhost:3000
```

---

## 🎯 Data Update Frequency

- **Stock Prices**: Every 1-2 minutes
- **NEPSE Index**: Every 1-2 minutes
- **Sector Indices**: Every 5 minutes
- **Historical Data**: Daily

All data is cached in-memory with 30-second TTL for real-time responsiveness.

---

**💡 Tip**: Keep both terminal windows visible to see real-time logs from backend and frontend!
