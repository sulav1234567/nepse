#!/bin/bash
# NEPSE-ALPHA - Production Run Script
# This script starts the entire NEPSE-ALPHA system with both backend and frontend

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         NEPSE-ALPHA REAL-TIME STOCK MARKET SYSTEM            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python and Node.js
echo -e "${YELLOW}[1/4] Checking Prerequisites...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js 20+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python and Node.js found${NC}"
echo ""

# Setup Python virtual environment
echo -e "${YELLOW}[2/4] Setting up Python environment...${NC}"
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install Python dependencies
if [ ! -f "backend/.deps_installed" ]; then
    echo "Installing Python dependencies..."
    pip install -q -r backend/requirements.txt
    touch backend/.deps_installed
fi
echo -e "${GREEN}✓ Python environment ready${NC}"
echo ""

# Setup Node.js dependencies
echo -e "${YELLOW}[3/4] Setting up Node.js environment...${NC}"
if [ ! -f ".deps_installed" ]; then
    echo "Installing Node.js dependencies..."
    npm ci --silent
    touch .deps_installed
fi
echo -e "${GREEN}✓ Node.js environment ready${NC}"
echo ""

# Start services
echo -e "${YELLOW}[4/4] Starting services...${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill %1 %2 2>/dev/null || true
    echo -e "${GREEN}Goodbye!${NC}"
}

trap cleanup EXIT

# Start backend
echo -e "${BLUE}Starting Backend API (FastAPI)...${NC}"
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 2
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}✗ Backend failed to start${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Backend running on http://127.0.0.1:8000${NC}"
echo ""

# Start frontend
echo -e "${BLUE}Starting Frontend (Next.js)...${NC}"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 5
echo -e "${GREEN}✓ Frontend running on http://localhost:3000${NC}"
echo ""

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}✓ NEPSE-ALPHA is running!${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "  📊 Dashboard:     ${YELLOW}http://localhost:3000${NC}"
echo -e "  🔌 API:            ${YELLOW}http://127.0.0.1:8000${NC}"
echo -e "  📖 API Docs:       ${YELLOW}http://127.0.0.1:8000/docs${NC}"
echo -e "  📡 Data Source:    ${YELLOW}Real-time NEPSE TMS (via Sharesansar)${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop the servers"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Wait for background processes
wait
