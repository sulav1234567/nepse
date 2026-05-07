# NEPSE-ALPHA Authentication System Setup & Deployment Guide

## Overview

This document provides complete instructions for setting up and deploying the NEPSE-ALPHA application with MongoDB authentication system.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [MongoDB Setup](#mongodb-setup)
4. [Running the Application](#running-the-application)
5. [API Documentation](#api-documentation)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Node.js**: v18+ ([Download](https://nodejs.org/))
- **Python**: 3.9+ ([Download](https://www.python.org/))
- **MongoDB**: v5.0+ ([Download](https://www.mongodb.com/try/download/community))
- **npm** or **yarn**: For Node.js package management

### System Requirements

- **RAM**: Minimum 4GB (8GB recommended)
- **Disk Space**: At least 2GB free
- **OS**: Windows, macOS, or Linux

---

## Local Development Setup

### Step 1: Install Dependencies

#### Backend (Python)

```bash
# Navigate to project root
cd /path/to/nepse-main

# Create a virtual environment (if not already done)
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install Python dependencies
pip install -r backend/requirements.txt
```

#### Frontend (Node.js)

```bash
# Install Node.js dependencies
npm install
```

### Step 2: Install MongoDB

#### macOS (using Homebrew)

```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install MongoDB
brew tap mongodb/brew
brew install mongodb-community

# Start MongoDB service
brew services start mongodb-community

# Verify installation
mongosh --version
```

#### Windows

1. Download MongoDB Community Edition from https://www.mongodb.com/try/download/community
2. Run the installer and follow the setup wizard
3. MongoDB should start automatically as a Windows Service
4. Verify: Open Command Prompt and run `mongosh --version`

#### Linux (Ubuntu/Debian)

```bash
# Add MongoDB repository
curl https://www.mongodb.org/static/pgp/server-7.0.asc | apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update and install
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod

# Enable auto-start
sudo systemctl enable mongod

# Verify
mongosh --version
```

### Step 3: Verify MongoDB Connection

```bash
# Open mongosh shell
mongosh

# In the mongosh shell, run:
db.version()

# If successful, you should see the MongoDB version
# Exit with: exit
```

---

## MongoDB Setup

### Create Database and Collections

```bash
# Open MongoDB shell
mongosh

# Use the nepse_alpha database (creates if doesn't exist)
use nepse_alpha

# Verify database was created
db.getCollectionNames()

# Create indexes (this is done automatically by the app on startup)
db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "username": 1 }, { unique: true })
```

### View User Data

```bash
# View all users
db.users.find({}).pretty()

# Find specific user
db.users.find({ email: "user@example.com" })

# Count users
db.users.countDocuments()
```

### Delete User (if needed)

```bash
# Delete by email
db.users.deleteOne({ email: "user@example.com" })

# Clear all users
db.users.deleteMany({})
```

---

## Running the Application

### Option 1: Manual Startup

#### Terminal 1 - Backend (FastAPI)

```bash
# From project root
source .venv/bin/activate  # macOS/Linux
# or .venv\Scripts\activate on Windows

cd backend
python -m uvicorn server:app --reload --port 8000
```

Backend will be available at: `http://127.0.0.1:8000`

#### Terminal 2 - Frontend (Next.js)

```bash
# From project root
npm run dev
```

Frontend will be available at: `http://localhost:3000`

### Option 2: Using Automated Script

```bash
# Make script executable (macOS/Linux)
chmod +x run.sh

# Run the script
./run.sh
```

The script will:
- Check prerequisites
- Install dependencies
- Start MongoDB (if needed)
- Start backend on port 8000
- Start frontend on port 3000

---

## API Documentation

### Authentication Endpoints

#### Register User

```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123",
  "full_name": "John Doe"  // Optional
}
```

**Response (201 Created):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "created_at": "2024-04-02T10:30:00",
    "is_active": true
  }
}
```

#### Login User

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "created_at": "2024-04-02T10:30:00",
    "is_active": true
  }
}
```

#### Get Current User

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "created_at": "2024-04-02T10:30:00",
  "is_active": true
}
```

#### Logout User

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

### Using Tokens in API Calls

All protected endpoints require the `Authorization` header:

```bash
curl -X GET http://127.0.0.1:8000/api/protected-endpoint \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

In JavaScript (frontend):

```javascript
const token = localStorage.getItem('access_token')

fetch('http://127.0.0.1:8000/api/protected-endpoint', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
```

---

## Production Deployment

### 1. Environment Configuration

#### Create `.env` file

```bash
# Backend
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/nepse_alpha
SECRET_KEY=your-very-long-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### 2. Update Security Settings

Edit `backend/auth.py` and change:

```python
# CHANGE THIS IN PRODUCTION!
SECRET_KEY = "your-secret-key-change-this-in-production"

# To something like:
SECRET_KEY = "generate-a-long-random-string-here"
```

Generate a secure key:
```python
import secrets
print(secrets.token_urlsafe(32))
```

### 3. Update Server Configuration

Edit `backend/database.py`:

```python
# For production with MongoDB Atlas:
MONGODB_URL = "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
DATABASE_NAME = "nepse_alpha"
```

### 4. Build Frontend

```bash
npm run build
```

### 5. Deployment Options

#### Option A: Heroku

```bash
# Install Heroku CLI
npm install -g heroku

# Login to Heroku
heroku login

# Create app
heroku create nepse-alpha

# Add MongoDB Atlas addon
heroku addons:create mongolab:sandbox

# Deploy
git push heroku main

# View logs
heroku logs --tail
```

#### Option B: AWS EC2

```bash
# SSH into EC2 instance
ssh -i key.pem ec2-user@instance-ip

# Install dependencies
sudo yum update
sudo yum install python3 nodejs

# Clone repository
git clone your-repo-url
cd nepse-main

# Follow local setup steps
```

#### Option C: DigitalOcean App Platform

1. Connect GitHub repository
2. Set environment variables
3. Configure build and run commands:
   - **Build**: `npm install && pip install -r backend/requirements.txt`
   - **Run**: Use process type file

#### Option D: Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Node.js
RUN apt-get update && apt-get install -y nodejs npm

# Copy requirements
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Install npm dependencies
RUN npm install
RUN npm run build

# Expose ports
EXPOSE 8000 3000

# Run script
CMD ["bash", "run.sh"]
```

Build and run:
```bash
docker build -t nepse-alpha .
docker run -p 8000:8000 -p 3000:3000 nepse-alpha
```

### 6. Setup MongoDB Atlas (Cloud)

1. Go to https://www.mongodb.com/cloud/atlas
2. Create free tier cluster
3. Set network access (IP whitelist)
4. Create database user
5. Get connection string
6. Update `MONGODB_URL` in environment

---

## Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
# macOS:
brew services list

# Linux:
sudo systemctl status mongod

# Windows:
Get-Service MongoDB

# Start MongoDB if not running
# macOS:
brew services start mongodb-community

# Linux:
sudo systemctl start mongod

# Windows:
net start MongoDB
```

### Port Already in Use

```bash
# Kill process on port 8000 (backend)
# macOS/Linux:
lsof -i :8000
kill -9 <PID>

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Kill process on port 3000 (frontend)
# Similar commands with port 3000
```

### Dependency Issues

```bash
# Clear pip cache and reinstall
pip install --no-cache-dir -r backend/requirements.txt

# Clear npm cache and reinstall
npm cache clean --force
npm install

# Upgrade npm
npm install -g npm@latest
```

### Authentication Issues

```bash
# Check MongoDB users collection
mongosh
use nepse_alpha
db.users.find({})

# Verify token format
# Token should be sent as: Authorization: Bearer <token>

# Check logs for errors
# Backend logs should show authentication attempts
```

### CORS Issues

If you see CORS errors, the backend CORS is already configured to allow all origins for development. For production, update `backend/server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Security Best Practices

### Production Checklist

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Enable HTTPS (use SSL certificate)
- [ ] Set strong MongoDB password
- [ ] Enable MongoDB network access restrictions
- [ ] Use environment variables for sensitive data
- [ ] Set CORS to specific domain
- [ ] Enable rate limiting
- [ ] Setup monitoring and logging
- [ ] Regular backups of MongoDB

### Token Security

- Tokens expire after 12 hours (configurable)
- Always send over HTTPS in production
- Store tokens in secure HTTP-only cookies (recommended for production)
- Never log tokens in console/logs

---

## Frontend Integration

### Using Auth in Components

```typescript
'use client'

import { useAuth } from '@/lib/auth-context'
import { redirect } from 'next/navigation'

export default function ProtectedPage() {
  const { user, isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <div>Loading...</div>
  if (!isAuthenticated) redirect('/auth/login')

  return (
    <div>
      <h1>Welcome, {user?.username}!</h1>
      <p>Email: {user?.email}</p>
    </div>
  )
}
```

### Making Authenticated API Calls

```typescript
const token = localStorage.getItem('access_token')

const response = await fetch('http://127.0.0.1:8000/api/protected-endpoint', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
```

---

## Support & Resources

- **MongoDB Documentation**: https://docs.mongodb.com/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Next.js Documentation**: https://nextjs.org/docs
- **JWT Authentication**: https://jwt.io/

---

## Version Info

- **App Version**: 1.0.0
- **Python**: 3.9+
- **Node.js**: 18+
- **MongoDB**: 5.0+
- **FastAPI**: 0.100+
- **Next.js**: 16.1+

---

**Last Updated**: April 2, 2026  
**Maintained by**: NEPSE-ALPHA Team
