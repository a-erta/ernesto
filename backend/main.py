import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .config import settings
from .models.db import Base, engine
from .api.routes import router
from .api.websocket import ws_router
from .api.credentials_routes import creds_router
from .api.device_routes import device_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ernesto.startup", local_dev=settings.LOCAL_DEV, use_s3=settings.use_s3, use_redis=settings.use_redis)
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

app.include_router(router)
app.include_router(ws_router)
app.include_router(creds_router)
app.include_router(device_router)

# Serve uploaded images locally (skipped when S3 is active)
if not settings.use_s3:
    uploads_dir = Path("./uploads")
    uploads_dir.mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
