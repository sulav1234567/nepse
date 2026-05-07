# NEPSE-ALPHA ULTIMATE - Deployment Guide

## Overview

NEPSE-ALPHA is a Five-Layer Stock Prediction Intelligence System for the Nepal Stock Exchange. It consists of:
- **Frontend**: Next.js 16 with React 19 (TypeScript)
- **Backend**: FastAPI (Python) with ML capabilities
- **Data Source**: Live NEPSE API with automatic demo fallback

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js)                      │
│  - Dashboard, Screener, Predictions, AI, Analysis, Portfolio│
│  - Fetches from Backend API via /api/live/*                 │
│  - Automatic fallback to demo data if backend unavailable   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                        │
│  - Real-time NEPSE data fetcher                            │
│  - Five-layer analysis engine                               │
│  - ML ensemble predictions (RF + XGBoost + GB)              │
│  - Portfolio optimization                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               NEPSE Official API                            │
│  https://nepalstock.com.np/api/nots                        │
│  - Today's prices, Market overview, Sector indices          │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Frontend
- Node.js 20+ and npm
- No additional configuration needed

### Backend
- Python 3.10+
- pip package manager

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/sulav1234567/nepse.git
cd nepse
```

### 2. Backend Setup

Install Python dependencies:
```bash
cd backend
pip install -r requirements.txt
```

**Backend Dependencies:**
- FastAPI, Uvicorn (API server)
- NumPy, Pandas, SciPy (numerical computing)
- Scikit-learn, XGBoost (machine learning)
- Statsmodels, Filterpy (statistical analysis)
- HTTPX (async HTTP client for NEPSE API)

### 3. Frontend Setup

Install Node.js dependencies:
```bash
cd ..  # Back to root directory
npm install
```

**Frontend Dependencies:**
- Next.js 16, React 19
- Recharts (data visualization)
- Lucide React (icons)

## Running the Application

### Development Mode

**Step 1: Start Backend Server**
```bash
cd backend
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

**Step 2: Start Frontend Development Server**

In a new terminal:
```bash
cd ..  # Back to root directory
npm run dev
```

The frontend will be available at: `http://localhost:3000`

### Production Mode

**Backend (Production)**
```bash
cd backend
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

**Frontend (Production)**
```bash
npm run build
npm run start
```

## Environment Configuration

### Frontend Environment Variables

Create `.env.local` in the root directory:

```env
# Backend API URL (optional - defaults to http://localhost:8000)
NEXT_PUBLIC_API_URL=http://localhost:8000

# For production deployment:
# NEXT_PUBLIC_API_URL=https://your-backend-api.com
```

### Backend Environment Variables

The backend uses environment variables for NEPSE API configuration (optional):

```bash
# Optional: NEPSE API credentials (if required in future)
export NEPSE_API_KEY=your_api_key_here
```

Currently, the backend accesses the public NEPSE API without authentication.

## Data Source Behavior

The application intelligently handles data sources:

### Automatic Fallback
1. **Primary**: Attempts to fetch live data from NEPSE API via backend
2. **Fallback**: Uses demo data if:
   - Backend is not running
   - NEPSE API is unavailable
   - Network errors occur

### Data Source Indicator
All pages display a badge showing the current data source:
- 🟢 **LIVE DATA** (green) - Real-time NEPSE data
- 🟡 **DEMO DATA** (yellow) - Fallback demo data

## API Endpoints

### Market Data
- `GET /api/live/stocks` - All stocks with real-time prices
- `GET /api/live/market` - Market overview and index
- `GET /api/market` - Market with regime detection
- `GET /api/market/sectors` - Sector performance

### Stock Analysis
- `GET /api/stocks` - All stocks with FCS scores
- `GET /api/stocks/{symbol}` - Full five-layer analysis
- `GET /api/stocks/{symbol}/history` - Historical prices

### Predictions
- `GET /api/predictions/daily` - Top 5 daily signals
- `GET /api/predictions/weekly` - Top 10 weekly positions
- `GET /api/predictions/monthly` - Top 5 monthly picks

### AI/ML
- `GET /api/ai/predictions` - ML ensemble predictions
- `GET /api/ai/prediction/{symbol}` - Stock-specific ML prediction
- `GET /api/ai/feature-importance` - Feature importance rankings

### Portfolio
- `GET /api/portfolio` - Optimized allocation

### Health
- `GET /api/health` - System status

## Docker Deployment (Optional)

### Backend Dockerfile
Create `backend/Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
cd backend
docker build -t nepse-backend .
docker run -p 8000:8000 nepse-backend
```

### Frontend Dockerfile
Create `Dockerfile` in root:

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

Build and run:
```bash
docker build -t nepse-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://backend:8000 nepse-frontend
```

### Docker Compose
Create `docker-compose.yml` in root:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped

  frontend:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped
```

Run with Docker Compose:
```bash
docker-compose up -d
```

## Troubleshooting

### Frontend can't connect to backend
**Problem**: Data badge shows "DEMO DATA" even when backend is running

**Solutions**:
1. Verify backend is running: `curl http://localhost:8000/api/health`
2. Check NEXT_PUBLIC_API_URL in `.env.local`
3. Check browser console for CORS or network errors
4. Ensure backend allows CORS (already configured in server.py)

### NEPSE API not responding
**Problem**: Backend logs show "NEPSE today-price fetch failed"

**Solutions**:
1. The app automatically falls back to demo data
2. Check NEPSE website is accessible: `curl https://nepalstock.com.np`
3. NEPSE API might be down during off-market hours
4. Token refresh might fail - this is handled gracefully

### Python dependencies fail to install
**Problem**: pip install fails for scipy or scikit-learn

**Solutions**:
1. Install system dependencies (Ubuntu/Debian):
   ```bash
   sudo apt-get update
   sudo apt-get install python3-dev build-essential gfortran libopenblas-dev
   ```
2. Use conda instead of pip:
   ```bash
   conda install numpy scipy scikit-learn statsmodels
   pip install -r requirements.txt
   ```

### XGBoost not available
**Problem**: XGBoost import fails

**Solution**: XGBoost is optional - ML predictions will use RandomForest and GradientBoosting only
```bash
pip install xgboost  # Install if needed
```

## Performance Optimization

### Backend
- **Caching**: NEPSE API responses cached for 60 seconds
- **Workers**: Use multiple Uvicorn workers in production (`--workers 4`)
- **Memory**: ML models loaded on-demand

### Frontend
- **Build optimization**: Next.js automatically optimizes bundles
- **Image optimization**: Use Next.js Image component for assets
- **Code splitting**: Pages loaded on-demand

## Monitoring

### Backend Logs
```bash
# View Uvicorn logs
tail -f uvicorn.log

# Health check monitoring
watch -n 5 curl http://localhost:8000/api/health
```

### Frontend Logs
Check browser developer console for:
- API request/response details
- Data source changes
- React component errors

## Security Considerations

### Production Checklist
- [ ] Set proper CORS origins in `server.py` (currently allows all)
- [ ] Use HTTPS for production deployment
- [ ] Set secure environment variables
- [ ] Enable rate limiting on API endpoints
- [ ] Monitor API usage
- [ ] Keep dependencies updated

### NEPSE API
- Currently uses public endpoints
- No authentication required
- Respects rate limits with caching

## Support

For issues and questions:
- GitHub Issues: https://github.com/sulav1234567/nepse/issues
- Check API documentation: http://localhost:8000/docs (when backend running)

## License

Check repository LICENSE file for details.
