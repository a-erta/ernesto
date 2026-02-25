# Ernesto — Agentic Second-Hand Selling Assistant

Ernesto automates the full lifecycle of selling second-hand items:
photo → AI analysis → listing generation → multi-platform publishing → inbox management → offer negotiation.

## Architecture

```
backend/
├── agents/         # LangGraph nodes (intake, listing, publisher, deal_manager)
├── platforms/      # Platform adapters (eBay REST API, Vinted Playwright stub)
├── models/         # SQLAlchemy DB models + Pydantic schemas
├── graph/          # LangGraph workflow definition
├── api/            # FastAPI routes + WebSocket manager
└── main.py         # App entrypoint

frontend/
└── src/
    ├── pages/      # Dashboard, ItemDetail
    ├── components/ # ApprovalPanel, OfferCard, AgentTimeline, ...
    ├── hooks/      # useItemSocket (WebSocket)
    └── lib/        # API client
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add OPENAI_API_KEY at minimum

uvicorn main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Configuration

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Required. GPT-4o for vision, GPT-4o-mini for copy |
| `EBAY_APP_ID` / `EBAY_CERT_ID` / `EBAY_USER_TOKEN` | eBay Sell API credentials |
| `EBAY_SANDBOX` | `true` for sandbox, `false` for production |
| `TELEGRAM_BOT_TOKEN` | Optional. For mobile offer notifications |

## Agent Pipeline

```
[Photo upload] → Intake Agent (GPT-4o vision)
                      ↓
              Listing Agent (comparables + copy generation)
                      ↓
         ⏸ HUMAN APPROVAL (review listing, set price)
                      ↓
              Publisher Agent (posts to platforms)
                      ↓
            Deal Manager Agent (monitors inbox)
                      ↓
         ⏸ HUMAN OFFER DECISION (accept / counter / decline)
                      ↓
                   [Sold]
```

## Platform Support

| Platform | Status | Method |
|---|---|---|
| eBay | Full implementation | Official REST API |
| Vinted | Stub (ready to implement) | Playwright automation |
| Depop | Stub | Playwright automation |

## Adding a New Platform

1. Create `backend/platforms/yourplatform.py` extending `BasePlatformAdapter`
2. Implement all abstract methods
3. Register in `backend/agents/listing.py` and `backend/agents/publisher.py`
