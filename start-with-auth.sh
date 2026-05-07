#!/bin/bash

# NEPSE-ALPHA Complete Start Script
# This script runs everything needed to start the application

set -e

echo "=================================================="
echo "🚀 NEPSE-ALPHA Complete Startup Script"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Change to project directory
cd /Users/sulavkhatiwada/Desktop/nepse-main

# Kill any existing processes on ports 8000 and 3000
echo -e "${BLUE}Cleaning up existing processes...${NC}"
lsof -i :8000 | grep -v COMMAND | awk '{print $2}' | xargs kill -9 2>/dev/null || true
lsof -i :3000 | grep -v COMMAND | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 2

# Verify MongoDB is running
echo -e "${BLUE}Checking MongoDB...${NC}"
if ! mongosh --eval "db.version()" > /dev/null 2>&1; then
    echo "MongoDB not running. Starting..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start mongodb-community 2>/dev/null || true
    fi
    sleep 2
fi
echo -e "${GREEN}✓ MongoDB OK${NC}"

# Setup Python environment
echo ""
echo -e "${BLUE}Setting up Python environment...${NC}"
source .venv/bin/activate || . .venv/Scripts/activate

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip install -q -r backend/requirements.txt
npm install -q 2>/dev/null || true
echo -e "${GREEN}✓ Dependencies OK${NC}"

# Start Backend
echo ""
echo -e "${BLUE}Starting Backend Server...${NC}"
cd backend
/Users/sulavkhatiwada/Desktop/nepse-main/.venv/bin/python -m uvicorn server:app --reload --port 8000 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Check if backend started successfully
if ! curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "Retrying backend..."
    sleep 3
fi

if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend running on http://127.0.0.1:8000${NC}"
else
    echo "⚠ Backend may not be responding - proceed with caution"
fi

# Start Frontend
echo ""
echo -e "${BLUE}Starting Frontend Server...${NC}"
npm run dev > /dev/null 2>&1 &
FRONTEND_PID=$!

sleep 3
echo -e "${GREEN}✓ Frontend running on http://localhost:3000${NC}"

echo ""
echo "=================================================="
echo -e "${GREEN}✅ Application Successfully Started!${NC}"
echo "=================================================="
echo ""
echo "📱 Frontend:  http://localhost:3000"
echo "🔌 Backend:   http://127.0.0.1:8000"
echo "📚 Docs:      http://127.0.0.1:8000/docs"
echo ""
echo "🔐 Auth Flow:"
echo "   1. Go to http://localhost:3000/auth/register"
echo "   2. Create a new account"
echo "   3. You'll be logged in and redirected to dashboard"
echo ""
echo "⚙️  MongoDB:"
echo "   mongosh"
echo "   use nepse_alpha"
echo "   db.users.find().pretty()"
echo ""
echo "🛑 To stop: Press Ctrl+C"
echo ""
echo "=================================================="

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
