"""Show broker-scrape progress + ETA. Run: python scripts/broker_progress.py"""
import glob, os, re

LOG = os.environ.get("BROKER_LOG", "/tmp/broker_scrape.log")
TOTAL = len(glob.glob("data/market/stocks/*.csv"))

if not os.path.exists(LOG):
    raise SystemExit(f"No log at {LOG} — is the scrape running?")

prog = [l for l in open(LOG) if "Progress:" in l]
last = prog[-1].strip() if prog else "(no progress yet)"
http = [l for l in open(LOG) if "HTTP Request" in l]
ts = [re.match(r"(\d+):(\d+):(\d+)", l) for l in http]
secs = [int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) for m in ts if m]
rate = len(secs) / max(max(secs) - min(secs), 1) if len(secs) > 1 else 0

m = re.search(r"Progress: (\d+)/(\d+) symbols", last)
done = int(m.group(1)) if m else len(glob.glob("data/broker/*.csv"))
req_per_sym = len(secs) / max(done, 1)
eta_h = (TOTAL - done) * req_per_sym / max(rate, 1) / 3600 if rate else float("inf")
running = bool(os.popen("pgrep -f scrape_broker_floorsheet").read().strip())

print(f"Scraper running: {'YES' if running else 'NO (stopped/finished)'}")
print(f"Symbols fetched: {done} / {TOTAL}  ({done/TOTAL*100:.0f}%)")
print(f"Rate:            {rate:.1f} req/sec")
print(f"Time remaining:  ~{eta_h:.1f} hours")
print(f"Latest:          {last.split('] ',1)[-1] if '] ' in last else last}")
