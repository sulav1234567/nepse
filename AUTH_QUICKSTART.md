# Quick Start: Authentication System

## 🚀 Get Started in 5 Minutes

### Prerequisites (Already Installed?)

```bash
# Check Python
python --version  # Must be 3.9+

# Check Node.js
node --version  # Must be 18+

# Check MongoDB
mongosh --version  # Must be installed
```

### Step 1: Activate Virtual Environment

```bash
cd /path/to/nepse-main

# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### Step 2: Start MongoDB

```bash
# macOS:
brew services start mongodb-community

# Linux:
sudo systemctl start mongod

# Windows:
net start MongoDB

# Verify:
mongosh --eval "db.version()"
```

### Step 3: Install New Dependencies

```bash
pip install -r backend/requirements.txt
npm install  # Already done? Just run if needed
```

### Step 4: Start Backend (Terminal 1)

```bash
cd backend
python -m uvicorn server:app --reload --port 8000
```

You should see: `✓ MongoDB connected successfully`

### Step 5: Start Frontend (Terminal 2)

```bash
# From project root
npm run dev
```

### Step 6: Test Authentication

#### Visit the App

Open: http://localhost:3000

Click "Create Account" or go to: http://localhost:3000/auth/register

#### Register a New User

```
Email: test@example.com
Username: testuser
Password: Test123456
Full Name: Test User
```

#### Login

```
Email: test@example.com
Password: Test123456
```

---

## 🔌 Test API Directly

### Register via cURL

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "password123",
    "full_name": "John Doe"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "email": "user@example.com",
    "username": "johndoe",
    ...
  }
}
```

### Login via cURL

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

### Get Current User Info

```bash
# Replace TOKEN with the access_token from response above
curl -X GET http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer TOKEN"
```

---

## 📱 Frontend Pages

| Page | URL | Description |
|------|-----|-------------|
| Register | `/auth/register` | New user signup |
| Login | `/auth/login` | User login |
| Dashboard | `/` | Main app (needs login) |

---

## 💾 MongoDB Data

### View Users in Database

```bash
# Open MongoDB shell
mongosh

# Select database
use nepse_alpha

# View all users
db.users.find({}).pretty()

# Count users
db.users.countDocuments()

# Find specific user
db.users.findOne({ email: "user@example.com" })
```

---

## ✅ Verification Checklist

- [ ] MongoDB is running (`mongosh` works)
- [ ] Backend starts without errors on port 8000
- [ ] Frontend starts on port 3000
- [ ] Can register new user at `/auth/register`
- [ ] Can login with registered credentials
- [ ] Can see user info after login
- [ ] Token is saved in localStorage

---

## 🐛 Common Issues

### MongoDB Connection Error

```
ConnectionFailure: [Errno 61] Connection refused
```

**Fix**: Start MongoDB
```bash
brew services start mongodb-community  # macOS
# or
sudo systemctl start mongod  # Linux
```

### Port 8000 Already in Use

```bash
# Find process
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Module Not Found Error

```bash
# Reinstall dependencies
pip install -r backend/requirements.txt
```

---

## 📚 Next Steps

1. ✅ Test login/register on frontend
2. ✅ Test API with cURL
3. Integrate auth into other pages
4. Add watchlist functionality
5. Add portfolio management
6. Deploy to production

See **AUTH_SETUP_DEPLOYMENT.md** for detailed setup and deployment instructions.

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `backend/auth.py` | JWT token and password management |
| `backend/database.py` | MongoDB connection and user operations |
| `backend/server.py` | API endpoints for auth |
| `src/app/auth/login/page.tsx` | Login page |
| `src/app/auth/register/page.tsx` | Register page |
| `src/lib/auth-context.tsx` | React context for auth state |

---

**Time to get running**: ~5 minutes ⚡
