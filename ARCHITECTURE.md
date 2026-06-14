# NEPSE ALPHA — Architecture & Engineering Roadmap

A senior-level map of how the system is built, how data flows from the market to a
trade, and a phased, risk-aware plan for the broker-automation and UX work.

---

## 1. System architecture (current)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Frontend — Next.js (App Router, React)                                      │
│  /landing (public)  /auth/*  │  /  (dashboard)  /ai-predictions  /screener   │
│  /analysis  /index-analysis  /portfolio  /trader  /audit  /autonomous        │
│  src/lib/api-client.ts  ·  auth-context (JWT in localStorage)                │
└───────────────┬──────────────────────────────────────────────────────────────┘
                │  HTTPS (Bearer JWT)
┌───────────────▼──────────────────────────────────────────────────────────────┐
│  Backend — FastAPI (backend/server.py + autonomous/api.py)                    │
│                                                                                │
│  Auth/security        backend/auth.py · backend/security.py (JWT, Fernet)     │
│  Live data            backend/nepse_fetcher.py  (Sharesansar live + EOD)      │
│  Five-layer engine    backend/engine.py · index_analysis · market_intelligence│
│  Autonomous platform  backend/autonomous/  (service, models, features, ...)   │
│  Broker               backend/broker/  (mero_share, tms_client, broker_api)   │
│  Persistence          SQLite/SQLAlchemy (market bars, macro) + MongoDB (users)│
└───────────────┬───────────────────────────────────┬──────────────────────────┘
                │                                   │
        ┌───────▼────────┐                  ┌───────▼─────────┐
        │ Market sources │                  │ Broker portals  │
        │ Sharesansar    │                  │ MeroShare (CDSC)│
        │ Merolagani     │                  │ TMS (NEPSE)     │
        └────────────────┘                  └─────────────────┘
```

### Key modules
- **`nepse_fetcher.py`** — single source of truth for live data. Intraday NEPSE
  index via the Sharesansar live-trading feed, accurate EOD fallback, persisted
  last-known value. No fabricated numbers; every figure carries
  `market_state / is_live / is_stale / as_of`.
- **`autonomous/`** — the ML platform. `service.AutonomousResearchPlatform`
  orchestrates ingestion → feature building → training → signals.
- **`broker/broker_api.py`** — unified buy/sell/portfolio over **paper** (default)
  or **live**. MeroShare (holdings) and TMS (orders) are separate clients.
- **`security.py`** — fail-closed JWT secret + Fernet at-rest encryption for
  broker credentials (no plaintext passwords, ever).

---

## 2. Data & ML pipeline

```
Ingest ─────────────► Engineer ─────────► Train ──────────► Serve / Act
live prices (334)     250 features         ensemble + seq    /api/ai/predictions
macro & global        technicals, beta,    + PPO meta        autonomous agent
fundamentals (CASA)   sector strength,     walk-forward      portfolio self-audit
news sentiment        macro correlations   validated (GPU)   broker execution
```

- **Features** (`autonomous/features.py`, `build_feature_frame`): ~250 columns —
  price/volume technicals, RSI/MACD/Bollinger/Ichimoku, beta/alpha vs NEPSE,
  sector relative strength, fundamentals (eps, roe, npl, **casa_ratio**), macro
  correlations (NIFTY, SP500, gold, oil, remittance, …), news sentiment.
  Label columns are **excluded from imputation** (the June-2026 leak fix).
- **Models** (`autonomous/models.py`): XGBoost + LightGBM ensemble, LSTM, a
  Temporal-Fusion-style net, a PPO RL agent, and a contextual meta-learner.
- **Training**: Colab GPU (`scripts/colab_continuous_train.py`, A100) — ingest +
  `train_models(force=True)` + walk-forward backtest; or local
  `scripts/train_local.py` (now wired to the same 248-feature schema).
- **Honesty note**: the previously-deployed model predated the leak fix; its
  ~90% accuracy was inflated. Post-fix metrics land in a realistic range — that's
  the number to trust.

---

## 3. Security model

| Concern | Current state | Notes |
|---|---|---|
| Passwords | bcrypt (12 rounds) | ✅ good |
| JWT signing key | `security.get_jwt_secret()` — **fail-closed in prod** | set `JWT_SECRET_KEY` |
| Broker credentials | **Fernet-encrypted at rest** (`security.encrypt_secret`) | set `CREDENTIAL_ENCRYPTION_KEY` |
| Token storage (frontend) | localStorage | ⚠️ XSS-exposed → migrate to httpOnly cookie (roadmap) |
| Transport | expects HTTPS/TLS termination | enforce in deployment |

**Required env for production**
```bash
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
CREDENTIAL_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
APP_ENV=production
```

---

## 4. Roadmap — broker automation & UX (phased, risk-gated)

### Phase 1 — Foundations ✅ (done this iteration)
- Fail-closed JWT, Fernet credential encryption (`security.py`).
- Public landing page + guest routing.
- Live intraday data, removal of all synthetic/fallback data, loaders.

### Phase 2 — MeroShare connect & self-audit (low risk, read-only)
- Per-user encrypted storage of **DP (depository participant) + username + password**.
- `POST /api/broker/meroshare/connect` → validate via `MeroShareClient.login()`,
  store ciphertext, return portfolio for the self-audit feature.
- **Dedicated MeroShare UI** (holdings, transactions, AI audit) — read-only, safe.

### Phase 3 — TMS account & manual trading (medium risk)
- Per-user encrypted TMS credentials; `TMSClient` session proxy.
- **Separate TMS UI** mirroring the broker workflow (order pad, open orders,
  portfolio, order book) — every action **user-initiated**, with confirmations.
- A full TMS "clone" is large; build incrementally (view → place → manage).

### Phase 4 — Autonomous execution (HIGH risk — gated)
- Scheduler that runs the agent and places trades **without the user present**.
- **Ships paper-mode only by default.** Live execution stays behind an explicit,
  per-user opt-in with hard risk limits (max position, daily cap, kill-switch).

### Cross-cutting — UI/UX overhaul
- Extract a shared design system (tokens, `<Card>`, `<Button>`, `<Loader>`,
  `<StatCard>`) from the inline styles; consistent nav, responsive, sharper data
  viz. Roll out page-by-page.

---

## 5. ⚠️ Legal / compliance (read before Phases 3–4)
- **Broker ToS**: TMS/MeroShare terms generally restrict credential sharing and
  automated/bot order placement. Storing a user's broker password and trading on
  their behalf may breach those terms and local securities regulation.
- **Recommendation**: treat live autonomous trading as opt-in, fully disclosed,
  with the user's explicit, informed consent and a one-tap kill-switch — and
  confirm it's permissible for your accounts before enabling.
