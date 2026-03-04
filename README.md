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
│   ├── auth.py               # JWT auth (Supabase in prod, bypassed in LOCAL_DEV)
│   ├── storage.py            # Image storage (local filesystem / S3)
│   ├── config.py             # Settings loaded from .env
│   ├── main.py               # App entrypoint
│   └── requirements.txt
├── frontend/                 # React + Vite web UI
│   └── src/
│       ├── pages/            # Dashboard, ItemDetail, Login
│       ├── components/       # ApprovalPanel, OfferCard, AgentTimeline, ...
│       ├── context/          # AuthContext (Supabase session)
│       ├── hooks/            # useItemSocket (WebSocket)
│       └── lib/              # API client, Supabase client
├── mobile/                   # React Native (Expo) iOS/Android app
│   └── src/
│       ├── screens/          # Dashboard, ItemDetail, NewItem, Settings, Login
│       ├── components/       # StatusBadge
│       ├── hooks/            # useItemWebSocket
│       ├── api/              # Axios client
│       ├── context/          # AuthContext (Supabase session)
│       └── navigation/       # Stack + tab navigator
├── Dockerfile                # Production container image
├── docker-compose.yml        # Full local stack (backend + PostgreSQL + Redis + frontend)
├── render.yaml               # Render Blueprint (one-click cloud deploy)
└── .github/workflows/
    └── deploy.yml            # CI/CD → ECR + ECS Fargate (manual trigger)
```

---

## Quick Start — Local Development (simplest)

> No authentication required locally. `LOCAL_DEV=true` is the default — the backend
> accepts all requests without a token and the frontend/mobile skip the login screen.

All commands run from the **project root** (`ernesto/`).

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

Open http://localhost:5173 — no login screen, goes straight to the dashboard.

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

## Authentication

### Local development (default)

`LOCAL_DEV=true` in `backend/.env` bypasses all authentication:
- The backend injects a hardcoded `local-user` for every request.
- The web frontend skips the login page entirely.
- The mobile app skips the login screen entirely.
- No Supabase account or credentials needed.

### Production — Supabase Auth

Supabase provides **Google SSO + email/password** sign-up out of the box.

#### Setup

1. Create a free project at https://supabase.com.
2. In your Supabase dashboard go to **Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL` (backend) / `VITE_SUPABASE_URL` (frontend) / `EXPO_PUBLIC_SUPABASE_URL` (mobile)
   - **anon/public key** → `SUPABASE_ANON_KEY` / `VITE_SUPABASE_ANON_KEY` / `EXPO_PUBLIC_SUPABASE_ANON_KEY`
   - **JWT Secret** → `SUPABASE_JWT_SECRET` (backend only — keep this secret)
3. To enable Google login: Supabase dashboard → **Authentication → Providers → Google** → add your OAuth credentials.
4. Set `LOCAL_DEV=false` in `backend/.env`.

#### Backend `.env` (production)

```
LOCAL_DEV=false
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
```

#### Frontend `.env` (production)

```
VITE_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

#### Mobile `.env` (production)

```
EXPO_PUBLIC_LOCAL_DEV=false
EXPO_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

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
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_JWT_SECRET` | JWT secret from Supabase dashboard (Settings → API) |
| `S3_BUCKET` | S3 bucket for image uploads |
| `CLOUDFRONT_DOMAIN` | CloudFront domain for image URLs |
| `AWS_REGION` | e.g. `us-east-1` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 |
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
   → generates platform-optimised copy + proposed description
          ↓
   ⏸ HUMAN APPROVAL (web or mobile)
   → review AI analysis and comparables
   → edit proposed description
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
| `POST /api/items/{id}/approve` | Approve listing with final price (+ optional description) |
| `POST /api/items/{id}/cancel` | Cancel and archive item |
| `GET /api/items/{id}/offers` | List offers |
| `POST /api/offers/{id}/decide` | Accept / decline / counter an offer |
| `GET /api/items/{id}/messages` | List buyer messages |
| `GET /api/items/{id}/listings` | List platform listings |
| `POST /api/listings/{id}/delist` | Remove a published listing from a platform |
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
- **Auth bypass:** `LOCAL_DEV=true` (default) injects a hardcoded `local-user` — no login required. Set `LOCAL_DEV=false` and configure Supabase for multi-user production use.
- **WebSockets:** In-memory by default (single process). Set `REDIS_URL` for multi-process / multi-container fan-out.
- **Vite proxy:** The frontend dev server proxies `/api` and `/ws` to `http://localhost:8000` automatically.
- **Mobile env:** `mobile/.env` is gitignored. Set `EXPO_PUBLIC_API_URL` to your machine's LAN IP when testing on a physical device.

---

## Deployment — Render (Docker, HTTPS for eBay OAuth)

Render is a good fit: it runs your **Docker** image, gives you **HTTPS** out of the box (so eBay accepts the OAuth callback URL), and the repo already has a Blueprint.

`render.yaml` defines:
- **ernesto-api** — Web Service with **Docker** (FastAPI backend)
- **ernesto-db** — PostgreSQL
- **ernesto-redis** — Redis

### 1. Push to GitHub

Commit and push your repo (including `render.yaml` and `Dockerfile`).

### 2. Create the Blueprint on Render

1. Go to **https://dashboard.render.com** → **New → Blueprint**.
2. Connect the GitHub account/repo that contains Ernesto.
3. Select the repo. Render will detect `render.yaml` and list the services (ernesto-api, ernesto-db, ernesto-redis).
4. Click **Apply** (you can leave env vars for the next step).

### 3. Set environment variables

In the Render dashboard, open the **ernesto-api** service → **Environment** and set every variable that is `sync: false` in the Blueprint. At minimum:

| Variable | What to set |
|----------|----------------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `SECRET_KEY` | (Optional — Render can auto-generate; or set your own long random string) |
| `CORS_ORIGINS` | Frontend origin(s), e.g. `https://your-frontend.onrender.com` or `http://localhost:5173` for local dev |
| `SUPABASE_URL` | Supabase project URL (if using auth) |
| `SUPABASE_JWT_SECRET` | From Supabase → Settings → API (if using auth) |
| `FERNET_KEY` | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `EBAY_PROD_APP_ID` | eBay production app ID |
| `EBAY_PROD_CERT_ID` | eBay production cert ID |
| `EBAY_OAUTH_REDIRECT_URI` | **eBay RuName** from Developer Portal (see step 4), not the callback URL |
| `EBAY_FULFILLMENT_POLICY_ID` / `EBAY_PAYMENT_POLICY_ID` / `EBAY_RETURN_POLICY_ID` | From `python test_ebay.py --prod` (optional if using OAuth only) |

`DATABASE_URL` and `REDIS_URL` are filled automatically from the PostgreSQL and Redis services.

### 4. First deploy and eBay OAuth (RuName)

eBay uses a **RuName** (Redirect URL name), not the raw callback URL, in the OAuth request.

1. Trigger a deploy and copy your API URL (e.g. `https://ernesto-api-xxxx.onrender.com`).
2. In **eBay Developer Portal** → Your app → **User Tokens** (next to Client ID) → **Get a Token from eBay via Your Application**:
   - If you have no Redirect URL, click to add one and complete the form.
   - Set **Auth Accepted URL** to: `https://ernesto-api-xxxx.onrender.com/api/auth/ebay/callback` (your real callback).
   - Set **Auth Declined URL** (e.g. your frontend or API root).
   - Save; eBay shows a **RuName** value (a string like `YourName-YourApp-PRD-xxxxx-xxxxx`).
3. In **Render** → ernesto-api → **Environment**, set:
   - `EBAY_OAUTH_REDIRECT_URI` = **that RuName value** (paste the RuName, not the callback URL).
4. Save and redeploy.

After that, “Connect eBay” opens eBay in a popup; when the user approves, eBay redirects to your callback, the backend saves the token and redirects to the frontend, the popup closes and the app shows "eBay connected". If you see eBay's "Thank you" page but the app never shows connected and publishing returns 401, check that **Auth Accepted URL** in the eBay portal is exactly `https://<your-api-host>/api/auth/ebay/callback` (with `callback`, not `call`).

### 5. Frontend (optional)

- **Option A:** Keep running the frontend locally (`npm run dev`) and set `CORS_ORIGINS=http://localhost:5173` so it can call the Render API.
- **Option B:** Deploy the frontend as a **Static Site** on Render (build command: `npm run build`, publish directory: `dist`), then set `CORS_ORIGINS` to that site’s URL (e.g. `https://ernesto.onrender.com`).

### Summary

| Step | Action |
|------|--------|
| 1 | Push repo (with `render.yaml`, `Dockerfile`) to GitHub |
| 2 | Render → New → Blueprint → connect repo → Apply |
| 3 | Set env vars for ernesto-api (OPENAI_API_KEY, FERNET_KEY, CORS_ORIGINS, eBay, etc.) |
| 4 | In eBay portal create a Redirect URL (Auth Accepted URL = your callback); set `EBAY_OAUTH_REDIRECT_URI` to the **RuName** |
| 5 | (Optional) Deploy frontend as Static Site or use local frontend with CORS |

> **Free tier:** Web services spin down after ~15 min idle (cold start ~30s). Starter plan ($7/mo) keeps the API always on.

### Subsequent deploys

Push to the branch connected to the Blueprint (usually `main`); Render redeploys the Docker image automatically.

---

## Deployment — AWS ECS (advanced)

The GitHub Actions workflow (`.github/workflows/deploy.yml`) is triggered **manually only** (workflow_dispatch) to avoid accidental deploys:

1. Runs tests
2. Builds Docker image and pushes to ECR
3. Updates ECS Fargate service with rolling deploy

Required GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
Required GitHub variables: `AWS_REGION`

Infrastructure needed: ECS cluster + service, ECR repository, RDS PostgreSQL, ElastiCache Redis, S3 bucket, Secrets Manager entries for all env vars.

---

## .github folder

The `.github/` folder **should be committed** to your repository. It contains the GitHub Actions workflow for AWS deployment. Since the workflow is set to `workflow_dispatch` only, it will never run automatically — it's safe to have in the repo and you trigger it manually from the GitHub Actions UI when needed.
