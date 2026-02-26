# ---- Build stage: install Python deps ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    asyncpg \
    "langgraph-checkpoint-postgres" \
    aioboto3 \
    "redis[asyncio]" \
    cryptography

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY backend/ ./backend/

# Playwright browsers (needed for Vinted/Depop scraping)
RUN pip install playwright && playwright install chromium --with-deps

RUN mkdir -p /app/uploads

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOCAL_DEV=false \
    PORT=8000

EXPOSE $PORT

# Render injects $PORT at runtime; fall back to 8000 for local Docker use
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
