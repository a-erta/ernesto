import traceback
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .config import settings
from .models.db import Base, engine
from .storage import get_upload_dir
from .api.routes import router
from .api.websocket import ws_router
from .api.credentials_routes import creds_router
from .api.device_routes import device_router
from .api.ebay_auth_routes import router as ebay_auth_router

log = structlog.get_logger()


def _mask_compare(s: str, head: int = 10, tail: int = 6) -> str:
    """Mask a secret for log comparison: show first and last chars so you can match with portal."""
    if not s or not s.strip():
        return "(empty)"
    s = s.strip()
    if len(s) <= head + tail:
        return s[:4] + ".." + s[-2:] if len(s) > 6 else "***"
    return s[:head] + ".." + s[-tail:]


def _mask_secret(s: str, head: int = 4, tail: int = 3) -> str:
    """Mask a secret: show only set/len and first/last few chars."""
    if not s or not s.strip():
        return "(empty)"
    s = s.strip()
    if len(s) <= head + tail:
        return "***" if len(s) <= 6 else s[:2] + ".." + s[-2:]
    return s[:head] + ".." + s[-tail:]


def _bootstrap_env_log() -> None:
    """Log all important env vars at bootstrap (masked) so you can verify secrets are loaded."""
    s = settings
    log.info(
        "ernesto.env_bootstrap",
        # Core
        LOCAL_DEV=s.LOCAL_DEV,
        DATABASE_URL_kind="postgresql" if s.use_postgres else "sqlite",
        SECRET_KEY_set=bool((s.SECRET_KEY or "").strip()),
        SECRET_KEY_len=len((s.SECRET_KEY or "").strip()),
        OPENAI_API_KEY_set=bool((s.OPENAI_API_KEY or "").strip()),
        OPENAI_API_KEY_mask=_mask_secret(s.OPENAI_API_KEY or "", 6, 4),
        PUBLIC_API_URL=(s.PUBLIC_API_URL or "").strip() or "(empty)",
        UPLOAD_DIR=(s.UPLOAD_DIR or "").strip(),
        CORS_ORIGINS_count=len(s.cors_origins_list),
        # Auth (Supabase)
        SUPABASE_URL_set=bool((s.SUPABASE_URL or "").strip()),
        SUPABASE_URL_domain=_mask_compare((s.SUPABASE_URL or "").strip(), 24, 8) if (s.SUPABASE_URL or "").strip() else "(empty)",
        SUPABASE_ANON_KEY_set=bool((s.SUPABASE_ANON_KEY or "").strip()),
        SUPABASE_JWT_SECRET_set=bool((s.SUPABASE_JWT_SECRET or "").strip()),
        # Storage
        use_s3=s.use_s3,
        S3_BUCKET=(s.S3_BUCKET or "").strip() or "(empty)",
        AWS_ACCESS_KEY_ID_set=bool((s.AWS_ACCESS_KEY_ID or "").strip()),
        # Redis
        use_redis=s.use_redis,
        REDIS_URL_set=bool((s.REDIS_URL or "").strip()),
        # Encryption
        FERNET_KEY_set=bool((s.FERNET_KEY or "").strip()),
        FERNET_KEY_len=len((s.FERNET_KEY or "").strip()),
        # eBay production
        EBAY_MARKETPLACE_ID=(s.EBAY_MARKETPLACE_ID or "EBAY_US").strip(),
        EBAY_PROD_APP_ID=_mask_compare((s.EBAY_PROD_APP_ID or "").strip(), 12, 8),
        EBAY_PROD_CERT_ID=_mask_compare((s.EBAY_PROD_CERT_ID or "").strip(), 12, 8),
        EBAY_PROD_CLIENT_SECRET=_mask_compare((s.EBAY_PROD_CLIENT_SECRET or "").strip(), 8, 6),
        EBAY_OAUTH_REDIRECT_URI=_mask_compare((s.EBAY_OAUTH_REDIRECT_URI or "").strip(), 12, 8),
        EBAY_FULFILLMENT_POLICY_ID=(s.EBAY_FULFILLMENT_POLICY_ID or "").strip() or "(empty)",
        EBAY_PAYMENT_POLICY_ID=(s.EBAY_PAYMENT_POLICY_ID or "").strip() or "(empty)",
        EBAY_RETURN_POLICY_ID=(s.EBAY_RETURN_POLICY_ID or "").strip() or "(empty)",
        EBAY_MERCHANT_LOCATION_KEY=(s.EBAY_MERCHANT_LOCATION_KEY or "").strip() or "(empty)",
        # Optional
        TELEGRAM_BOT_TOKEN_set=bool((s.TELEGRAM_BOT_TOKEN or "").strip()),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ernesto.startup", local_dev=settings.LOCAL_DEV, use_s3=settings.use_s3, use_redis=settings.use_redis)
    _bootstrap_env_log()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    log.info("ernesto.shutdown")
    await engine.dispose()


app = FastAPI(
    title="Ernesto",
    description="Agentic second-hand selling assistant",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.head("/")
def root():
    """API is up. Use /docs for interactive docs. HEAD supported for Render health checks."""
    return {"service": "ernesto", "docs": "/docs", "health": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """No favicon; avoid 404 in logs when browser requests it."""
    return Response(status_code=204)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    """Log full traceback for 500s so Render logs show the cause."""
    log.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


app.include_router(router)
app.include_router(ws_router)
app.include_router(creds_router)
app.include_router(device_router)
app.include_router(ebay_auth_router)

# Serve uploaded images locally (skipped when S3 is active)
if not settings.use_s3:
    app.mount("/uploads", StaticFiles(directory=str(get_upload_dir())), name="uploads")
