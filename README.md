# Ernesto — Agentic Second-Hand Selling Assistant

Ernesto automates the full lifecycle of selling second-hand items:
photo → AI analysis → listing generation → multi-platform publishing → inbox management → offer negotiation.

## Architecture

```
ernesto/
├── backend/
│   ├── agents/         # LangGraph nodes (intake, listing, publisher, deal_manager)
│   ├── platforms/      # Platform adapters (eBay REST API, Vinted Playwright stub)
│   ├── models/         # SQLAlchemy DB models + Pydantic schemas
│   ├── graph/          # LangGraph workflow definition
│   ├── api/            # FastAPI routes + WebSocket manager
│   ├── config.py       # Settings (loaded from .env)
│   ├── main.py         # App entrypoint
│   └── requirements.txt
└── frontend/
    └── src/
        ├── pages/      # Dashboard, ItemDetail
        ├── components/ # ApprovalPanel, OfferCard, AgentTimeline, ...
        ├── hooks/      # useItemSocket (WebSocket)
        └── lib/        # API client
```

## Quick Start

> **Important:** all commands must be run from the **project root** (`ernesto/`), not from inside `backend/`.

### 1. Backend

```bash
# From the ernesto/ root
cd /path/to/ernesto

# Create and activate the virtual environment (first time only)
python3 -m venv backend/.venv
source backend/.venv/bin/activate

# Install dependencies (first time only)
pip install -r backend/requirements.txt

# Configure environment (first time only)
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY at minimum

# Start the server
uvicorn backend.main:app --reload
```

The API will be available at http://localhost:8000

### 2. Frontend

```bash
# In a separate terminal, from the ernesto/ root
cd frontend
npm install       # first time only
npm run dev
```

Open http://localhost:5173

---

## Configuration

Edit `backend/.env`. All variables except `OPENAI_API_KEY` are optional for local development.

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | GPT-4o for photo analysis, GPT-4o-mini for listing copy |
| `EBAY_APP_ID` | For eBay | From https://developer.ebay.com |
| `EBAY_CERT_ID` | For eBay | eBay API credentials |
| `EBAY_USER_TOKEN` | For eBay | OAuth user token with `sell.*` scopes |
| `EBAY_SANDBOX` | No | `true` (default) uses eBay sandbox; set `false` for production |
| `TELEGRAM_BOT_TOKEN` | No | Optional mobile notifications via Telegram bot |
| `TELEGRAM_CHAT_ID` | No | Your Telegram chat ID |
| `DATABASE_URL` | No | Defaults to `sqlite+aiosqlite:///./ernesto.db` |

---

## Agent Pipeline

```
[Photo upload + description]
          ↓
   Intake Agent (GPT-4o vision)
   → identifies item, brand, condition, features
          ↓
   Listing Agent
   → fetches sold comparables for pricing
   → generates platform-optimised copy
          ↓
   ⏸ HUMAN APPROVAL
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
   ⏸ HUMAN OFFER DECISION
   → accept / counter / decline each offer
          ↓
        [Sold]
```

LangGraph persists the full state in `ernesto_checkpoints.db` (SQLite), so the pipeline survives server restarts and can manage multiple items concurrently.

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

## Development Notes

- The SQLite application database is created automatically at `ernesto/ernesto.db` on first startup
- Uploaded images are stored in `ernesto/uploads/` and served at `/uploads/<filename>`
- LangGraph checkpoint state is stored in `ernesto/ernesto_checkpoints.db`
- The frontend proxies `/api` and `/ws` to `http://localhost:8000` via Vite's dev server config
