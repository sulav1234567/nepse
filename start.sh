#!/bin/bash

# NEPSE-ALPHA Quick Start Script
# This script starts both backend and frontend servers

echo "🚀 NEPSE-ALPHA ULTIMATE - Quick Start"
echo "======================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+ first."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 20+ first."
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Install backend dependencies if needed
if [ ! -d "backend/__pycache__" ]; then
    echo "📦 Installing backend dependencies..."
    cd backend
    pip install -r requirements.txt
    cd ..
    echo "✅ Backend dependencies installed"
    echo ""
fi

# Install frontend dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
    echo "✅ Frontend dependencies installed"
    echo ""
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Start backend server
echo "🔧 Starting Backend Server (FastAPI)..."
cd backend
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 3

# Check if backend started successfully
if ps -p $BACKEND_PID > /dev/null; then
    echo "✅ Backend running at http://localhost:8000"
    echo "   API docs: http://localhost:8000/docs"
else
    echo "❌ Backend failed to start. Check backend.log for errors."
    exit 1
fi

echo ""

# Start frontend server
echo "🎨 Starting Frontend Server (Next.js)..."
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 5

# Check if frontend started successfully
if ps -p $FRONTEND_PID > /dev/null; then
    echo "✅ Frontend running at http://localhost:3000"
else
    echo "❌ Frontend failed to start. Check frontend.log for errors."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "======================================"
echo "🎉 NEPSE-ALPHA is now running!"
echo "======================================"
echo ""
echo "📊 Dashboard:    http://localhost:3000"
echo "🔧 Backend API:  http://localhost:8000"
echo "📖 API Docs:     http://localhost:8000/docs"
echo ""
echo "💡 Data source will be LIVE if backend can connect to NEPSE API"
echo "   Otherwise, it will automatically use DEMO data"
echo ""
echo "📝 Logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "======================================"

# Wait for user interrupt
wait
