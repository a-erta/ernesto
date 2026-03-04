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


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ernesto.startup", local_dev=settings.LOCAL_DEV, use_s3=settings.use_s3, use_redis=settings.use_redis)
    # Log eBay OAuth env (masked) so you can compare with Developer Portal when debugging
    app_id = (settings.EBAY_PROD_APP_ID or "").strip()
    secret = (settings.EBAY_PROD_CLIENT_SECRET or "").strip()
    cert_id = (settings.EBAY_PROD_CERT_ID or "").strip()
    ru = (settings.EBAY_OAUTH_REDIRECT_URI or "").strip()
    log.info(
        "ernesto.ebay_oauth_config",
        prod_app_id=_mask_compare(app_id, 12, 8),
        prod_app_id_len=len(app_id),
        prod_client_secret=_mask_compare(secret, 8, 6),
        prod_client_secret_len=len(secret),
        prod_cert_id=_mask_compare(cert_id, 12, 8),
        prod_cert_id_len=len(cert_id),
        redirect_uri=_mask_compare(ru, 12, 8),
        redirect_uri_len=len(ru),
    )
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
def root():
    """API is up. Use /docs for interactive docs."""
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
