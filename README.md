# Ernesto — Agentic Second-Hand Selling Assistant

Ernesto automates the full lifecycle of selling second-hand items:
photo → AI analysis → listing generation → multi-platform publishing → inbox management → offer negotiation.

Manage everything from a **web browser** or the **iOS/Android mobile app**.

---

## Architecture

```
ernesto/
├── backend/
│   ├── agents/               # LangGraph nodes (intake, listing, publisher, deal_manager)
│   ├── platforms/            # Platform adapters (eBay REST API, Vinted Playwright stub)
│   ├── models/               # SQLAlchemy DB models + Pydantic schemas
│   ├── graph/                # LangGraph workflow definition
│   ├── api/
│   │   ├── routes.py         # Items, offers, messages, listings
│   │   ├── websocket.py      # Real-time updates (in-memory / Redis)
│   │   ├── credentials_routes.py  # Per-user platform credentials
│   │   └── device_routes.py  # Push notification device registration
│   ├── auth.py               # JWT auth (Cognito in prod, bypassed in LOCAL_DEV)
│   ├── storage.py            # Image storage (local filesystem / S3)
│   ├── config.py             # Settings loaded from .env
│   ├── main.py               # App entrypoint
│   └── requirements.txt
├── frontend/                 # React + Vite web UI
│   └── src/
│       ├── pages/            # Dashboard, ItemDetail
│       ├── components/       # ApprovalPanel, OfferCard, AgentTimeline, ...
│       ├── hooks/            # useItemSocket (WebSocket)
│       └── lib/              # API client
├── mobile/                   # React Native (Expo) iOS/Android app
│   └── src/
│       ├── screens/          # Dashboard, ItemDetail, NewItem, Settings
│       ├── components/       # StatusBadge
│       ├── hooks/            # useItemWebSocket
│       ├── api/              # Axios client
│       ├── context/          # AuthContext
│       └── navigation/       # Stack + tab navigator
├── Dockerfile                # Production container image
├── docker-compose.yml        # Full local stack (backend + PostgreSQL + Redis + frontend)
└── .github/workflows/
    └── deploy.yml            # CI/CD → ECR + ECS Fargate
```

---

## Quick Start — Local Development (simplest)

> All commands run from the **project root** (`ernesto/`).

### 1. Backend

```bash
# Create virtual environment (first time only)
python3 -m venv backend/.venv
source backend/.venv/bin/activate

# Install dependencies (first time only)
pip install -r backend/requirements.txt

# Configure environment (first time only)
cp backend/.env.example backend/.env
# Edit backend/.env — set OPENAI_API_KEY at minimum

# Start the server (accessible on all interfaces for mobile testing)
uvicorn backend.main:app --reload --host 0.0.0.0
```

API available at http://localhost:8000 · Docs at http://localhost:8000/docs

### 2. Web Frontend

```bash
# In a separate terminal
cd frontend
npm install       # first time only
npm run dev
```

Open http://localhost:5173

### 3. Mobile App (iOS / Android)

```bash
cd mobile
npx expo start
```

Scan the QR code with **Expo Go** (App Store / Google Play).

> **Phone on the same WiFi?** Update `mobile/.env` to use your Mac's local IP:
> ```
> EXPO_PUBLIC_API_URL=http://192.168.1.x:8000
> ```
> Find your IP with: `ipconfig getifaddr en0`

---

## Quick Start — Full Cloud-like Stack (Docker)

Runs backend + PostgreSQL + Redis + Vite frontend together. Requires Docker Desktop.

```bash
export OPENAI_API_KEY=sk-...
docker compose up --build
```

| Service    | URL                    |
|------------|------------------------|
| Web UI     | http://localhost:5173  |
| API        | http://localhost:8000  |
| PostgreSQL | localhost:5432         |
| Redis      | localhost:6379         |

---

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill in the values you need.

### Minimum (local dev)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | GPT-4o for photo analysis and listing copy |

`LOCAL_DEV=true` is the default — auth is bypassed, SQLite is used, images go to `./uploads/`.

### eBay integration

| Variable | Description |
|---|---|
| `EBAY_APP_ID` | From https://developer.ebay.com |
| `EBAY_CERT_ID` | eBay API credentials |
| `EBAY_USER_TOKEN` | OAuth user token with `sell.*` scopes |
| `EBAY_SANDBOX` | `true` (default) = sandbox; `false` = live |

### Cloud / production

| Variable | Description |
|---|---|
| `LOCAL_DEV` | Set to `false` to enable auth, S3, Redis |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` |
| `AWS_REGION` | e.g. `us-east-1` |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID |
| `COGNITO_APP_CLIENT_ID` | Cognito App Client ID |
| `S3_BUCKET` | S3 bucket for image uploads |
| `CLOUDFRONT_DOMAIN` | CloudFront domain for image URLs |
| `REDIS_URL` | `redis://host:6379` for pub/sub WebSockets |
| `FERNET_KEY` | Encryption key for stored platform credentials |

Generate a Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Agent Pipeline

```
[Photo upload + description]
          ↓
   Intake Agent (GPT-4o vision)
   → identifies item, brand, condition, features
   → falls back to text-only if image is refused
   → falls back to placeholder if description only
          ↓
   Listing Agent
   → fetches sold comparables for pricing
   → generates platform-optimised copy
          ↓
   ⏸ HUMAN APPROVAL (web or mobile)
   → review AI analysis and comparables
   → adjust price, then approve or cancel
          ↓
   Publisher Agent
   → posts to all selected platforms via adapters
          ↓
   Deal Manager Agent (polling loop)
   → auto-replies to buyer questions
   → surfaces new offers with AI recommendation
          ↓
   ⏸ HUMAN OFFER DECISION (web or mobile)
   → accept / counter / decline each offer
          ↓
        [Sold]
```

LangGraph persists the full pipeline state in `ernesto_checkpoints.db` (SQLite) or PostgreSQL (cloud), so it survives server restarts and manages multiple items and users concurrently.

---

## Platform Support

| Platform | Status | Method |
|---|---|---|
| eBay | Full implementation | Official REST API (`/sell/inventory`, `/sell/negotiation`) |
| Vinted | Stub — ready to implement | Playwright browser automation |
| Depop | Stub — ready to implement | Playwright browser automation |

### Adding a New Platform

1. Create `backend/platforms/yourplatform.py` extending `BasePlatformAdapter`
2. Implement all abstract methods (`post_listing`, `get_offers`, `get_messages`, etc.)
3. Register the adapter in `backend/agents/listing.py` and `backend/agents/publisher.py`

---

## API Reference

Full interactive docs at http://localhost:8000/docs when the backend is running.

| Endpoint | Description |
|---|---|
| `POST /api/items` | Upload photos + description, start pipeline |
| `GET /api/items` | List all items for current user |
| `GET /api/items/{id}` | Get item detail |
| `DELETE /api/items/{id}` | Delete item |
| `POST /api/items/{id}/approve` | Approve listing with final price |
| `POST /api/items/{id}/cancel` | Cancel and archive item |
| `GET /api/items/{id}/offers` | List offers |
| `POST /api/offers/{id}/decide` | Accept / decline / counter an offer |
| `GET /api/items/{id}/messages` | List buyer messages |
| `GET /api/items/{id}/listings` | List platform listings |
| `PUT /api/credentials/ebay` | Save eBay credentials |
| `PUT /api/credentials/vinted` | Save Vinted credentials |
| `DELETE /api/credentials/{platform}` | Remove credentials |
| `POST /api/devices` | Register device for push notifications |
| `WS /ws/{item_id}` | Real-time pipeline events |

---

## Development Notes

- **Database:** Created automatically at `ernesto.db` on first startup. Delete it to reset the schema after model changes.
- **Checkpoints:** LangGraph state stored in `ernesto_checkpoints.db`. Delete alongside `ernesto.db` when resetting.
- **Uploads:** Images stored in `./uploads/` locally, served at `/uploads/<filename>`. Set `S3_BUCKET` to use S3 instead.
- **Auth bypass:** `LOCAL_DEV=true` (default) injects a hardcoded `local-user` — no login required. Set `LOCAL_DEV=false` and configure Cognito for multi-user production use.
- **WebSockets:** In-memory by default (single process). Set `REDIS_URL` for multi-process / multi-container fan-out.
- **Vite proxy:** The frontend dev server proxies `/api` and `/ws` to `http://localhost:8000` automatically.
- **Mobile env:** `mobile/.env` is gitignored. Set `EXPO_PUBLIC_API_URL` to your machine's LAN IP when testing on a physical device.

---

## Deployment — Render (recommended, simple)

`render.yaml` in the repo root defines the full infrastructure as a Blueprint:
- **ernesto-api** — Docker web service (the FastAPI backend)
- **ernesto-db** — PostgreSQL database
- **ernesto-redis** — Redis (for WebSocket pub/sub)

### Steps

1. Push your code to GitHub (make sure `render.yaml` is committed).
2. Go to https://dashboard.render.com → **New → Blueprint**.
3. Connect your GitHub repo — Render reads `render.yaml` automatically.
4. In the environment variable screen, fill in the secrets marked `sync: false`:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI key |
| `CORS_ORIGINS` | Your frontend URL, e.g. `https://ernesto.onrender.com` |
| `FERNET_KEY` | Run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `EBAY_APP_ID` / `EBAY_CERT_ID` / `EBAY_USER_TOKEN` | eBay developer credentials (optional) |
| `COGNITO_USER_POOL_ID` / `COGNITO_APP_CLIENT_ID` | Only if you want real auth (optional) |
| `S3_BUCKET` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Only if you want S3 image storage (optional) |

5. Click **Apply** — Render provisions everything and deploys automatically.

`DATABASE_URL` and `REDIS_URL` are wired up automatically from the other services — you don't set those manually.

> **Free tier note:** Render's free web services spin down after 15 minutes of inactivity (cold start ~30s). Upgrade to the Starter plan ($7/mo) for always-on.

### Subsequent deploys

Every push to `main` triggers an automatic redeploy on Render. No extra CI/CD setup needed.

### Environment variables after deploy

Set `LOCAL_DEV=false` (already the default in `render.yaml`). With PostgreSQL and Redis wired in, the app runs fully multi-tenant with persistent storage and real-time WebSockets.

If you don't configure Cognito, set `LOCAL_DEV=true` temporarily — but note this means all requests share a single `local-user` account, which is fine for solo use.

---

## Deployment — AWS ECS (advanced)

Push to `main` triggers the GitHub Actions workflow (`.github/workflows/deploy.yml`):

1. Runs tests
2. Builds Docker image and pushes to ECR
3. Updates ECS Fargate service with rolling deploy

Required GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
Required GitHub variables: `AWS_REGION`

Infrastructure needed: ECS cluster + service, ECR repository, RDS PostgreSQL, ElastiCache Redis, S3 bucket, Cognito User Pool, Secrets Manager entries for all env vars.
