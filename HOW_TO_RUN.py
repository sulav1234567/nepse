#!/usr/bin/env python3
"""
NEPSE-ALPHA - Command Reference
Quick reference for running the app in different scenarios
"""

import os
import platform

def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")

def print_command(desc, cmd):
    print(f"  {desc}:")
    print(f"    {cmd}\n")

def main():
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "NEPSE-ALPHA - HOW TO RUN THE APP" + " "*20 + "║")
    print("╚" + "="*68 + "╝")
    
    project_path = "/Users/sulavkhatiwada/Desktop/nepse-main"
    
    print_section("🚀 QUICKEST WAY (Recommended - One Command)")
    print_command(
        "Run everything automatically",
        f"cd {project_path} && bash run.sh"
    )
    
    print_section("📱 MANUAL: TWO TERMINAL WINDOWS")
    print_command(
        "Terminal 1 - Backend API",
        f"cd {project_path} && source .venv/bin/activate && "
        "python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000"
    )
    print_command(
        "Terminal 2 - Frontend Dashboard",
        f"cd {project_path} && npm run dev"
    )
    
    print_section("🛠️ SETUP (First Time Only)")
    print_command(
        "Create Python environment",
        f"cd {project_path} && python3 -m venv .venv"
    )
    print_command(
        "Activate Python environment",
        "source .venv/bin/activate"
    )
    print_command(
        "Install Python dependencies",
        f"cd {project_path} && pip install -r backend/requirements.txt"
    )
    print_command(
        "Install Node dependencies",
        f"cd {project_path} && npm ci"
    )
    
    print_section("🧪 TESTING")
    print_command(
        "Test real-time data fetching",
        f"cd {project_path} && source .venv/bin/activate && python test_nepse_api.py"
    )
    print_command(
        "Debug NEPSE API",
        f"cd {project_path} && source .venv/bin/activate && python debug_nepse_api.py"
    )
    
    print_section("🌐 ACCESS POINTS (After running)")
    print("  Dashboard:      http://localhost:3000")
    print("  API:            http://127.0.0.1:8000")
    print("  API Docs:       http://127.0.0.1:8000/docs")
    print("  Health Check:   http://127.0.0.1:8000/api/health")
    
    print_section("⚡ INDIVIDUAL COMMANDS")
    print_command(
        "Just backend",
        f"cd {project_path} && source .venv/bin/activate && "
        "python -m uvicorn backend.server:app --reload --host 127.0.0.1 --port 8000"
    )
    print_command(
        "Just frontend",
        f"cd {project_path} && npm run dev"
    )
    print_command(
        "Build frontend for production",
        f"cd {project_path} && npm run build"
    )
    
    print_section("🔴 TROUBLESHOOTING")
    print_command(
        "Clear Node modules and reinstall",
        f"cd {project_path} && rm -rf node_modules && npm ci"
    )
    print_command(
        "Recreate Python environment",
        f"cd {project_path} && rm -rf .venv && python3 -m venv .venv && "
        "source .venv/bin/activate && pip install -r backend/requirements.txt"
    )
    print_command(
        "Kill processes using port 8000",
        "killall python3  # or: lsof -i :8000 | grep -v PID | awk '{print $2}' | xargs kill -9"
    )
    print_command(
        "Kill processes using port 3000",
        "killall node  # or: lsof -i :3000 | grep -v PID | awk '{print $2}' | xargs kill -9"
    )
    
    print_section("📊 DATA FETCHING FLOW")
    print("""  NEPSE-ALPHA fetches real-time NEPSE TMS data with fallbacks:
  
  1. NEPSE API (Official)
     └─ If unavailable...
  
  2. Sharesansar (Real-time web scraper) ✓ PRIMARY ACTIVE
     • Updates: Every 1-2 minutes
     • Data: Stock prices, NEPSE Index, market summary
     • Status: WORKING & TESTED
     └─ If unavailable...
  
  3. Merolagani (Web scraper backup)
     • Updates: Hourly
     • Data: Stock prices, indices
  
  ✓ System automatically falls back to ensure continuous operation
  ✓ Cache TTL: 30 seconds for real-time data
  ✓ SSL verification: Handled automatically
    """)
    
    print_section("💾 KEY FILES")
    print(f"""  {project_path}/
  ├── run.sh                   ← Quick start script (RECOMMENDED)
  ├── backend/
  │   ├── server.py            ← FastAPI server
  │   ├── nepse_fetcher.py     ← Real-time data fetching (UPDATED)
  │   ├── engine.py            ← Analysis engine
  │   └── requirements.txt      ← Python packages
  ├── src/
  │   ├── app/
  │   └── components/          ← React components
  ├── package.json             ← Node packages
  ├── test_nepse_api.py        ← Data fetch testing
  └── RUN_APP.md               ← Detailed docs
    """)
    
    print_section("ℹ️  LATEST UPDATE")
    print("""  Changes made to nepse_fetcher.py:
  ✓ NEPSE API now PRIMARY source (attempts first)
  ✓ Improved authentication & SSL handling
  ✓ Cache TTL reduced to 30 seconds (more real-time)
  ✓ Better error handling with proper fallback chain
  ✓ Sharesansar & Merolagani as reliable fallbacks
  ✓ Detailed logging for debugging
    """)
    
    print("\n" + "="*70)
    print("  For more details, see: RUN_APP.md")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
