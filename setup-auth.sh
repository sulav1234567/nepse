#!/bin/bash

# NEPSE-ALPHA Authentication Setup Script
# This script helps set up the authentication system with MongoDB

set -e

echo "🚀 NEPSE-ALPHA Authentication Setup"
echo "===================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
echo -n "Checking Python... "
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Found Python ${PY_VERSION}${NC}"
else
    echo -e "${RED}✗ Python not found${NC}"
    exit 1
fi

# Check Node.js
echo -n "Checking Node.js... "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓ Found ${NODE_VERSION}${NC}"
else
    echo -e "${RED}✗ Node.js not found${NC}"
    exit 1
fi

# Check MongoDB
echo -n "Checking MongoDB... "
if command -v mongosh &> /dev/null; then
    MONGO_VERSION=$(mongosh --version 2>&1 | head -1)
    echo -e "${GREEN}✓ Found ${MONGO_VERSION}${NC}"
else
    echo -e "${RED}✗ MongoDB not found${NC}"
    echo "Install from: https://www.mongodb.com/try/download/community"
    exit 1
fi

echo ""
echo "📦 Installing Python Dependencies..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate 2>/dev/null

# Upgrade pip
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# Install requirements
pip install -r backend/requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo ""
echo "📦 Installing Node Dependencies..."
npm install > /dev/null 2>&1
echo -e "${GREEN}✓ Node dependencies installed${NC}"

echo ""
echo "💾 Starting MongoDB..."

# Check if MongoDB is running
if ! mongosh --eval "db.version()" > /dev/null 2>&1; then
    echo "MongoDB is not running. Attempting to start..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew services start mongodb-community 2>/dev/null || true
            sleep 2
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo systemctl start mongod 2>/dev/null || true
        sleep 2
    fi
    
    # Check again
    if mongosh --eval "db.version()" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ MongoDB started${NC}"
    else
        echo -e "${YELLOW}⚠ MongoDB could not be started automatically${NC}"
        echo "Please start MongoDB manually and try again"
        exit 1
    fi
else
    echo -e "${GREEN}✓ MongoDB is running${NC}"
fi

echo ""
echo "🗄️  Setting up MongoDB Database..."

# Create database and indexes
mongosh << EOF > /dev/null 2>&1
use nepse_alpha
db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "username": 1 }, { unique: true })
EOF

echo -e "${GREEN}✓ Database initialized${NC}"

echo ""
echo "🔐 Generating Secret Key..."

# Generate secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || echo "your-secret-key-change-this")

echo -e "${YELLOW}Generated Secret Key: ${SECRET_KEY}${NC}"
echo "Update this in backend/auth.py SECRET_KEY variable"

echo ""
echo "✅ Setup Complete!"
echo ""
echo "Next steps:"
echo "==========="
echo ""
echo "1. Terminal 1 - Start Backend:"
echo "   cd backend"
echo "   python -m uvicorn server:app --reload --port 8000"
echo ""
echo "2. Terminal 2 - Start Frontend:"
echo "   npm run dev"
echo ""
echo "3. Open http://localhost:3000 in your browser"
echo ""
echo "4. Register at http://localhost:3000/auth/register"
echo ""
echo "For more details, see Auth_QUICKSTART.md or AUTH_SETUP_DEPLOYMENT.md"
echo ""
