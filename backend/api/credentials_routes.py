"""
Platform credentials API.
Users connect their eBay / Vinted accounts here.
Credentials are encrypted at rest with Fernet.
"""
import json
import structlog
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..auth import get_current_user, AuthUser
from ..models.db import get_db, DBPlatformCredential
from ..config import settings

log = structlog.get_logger()
creds_router = APIRouter(prefix="/api/credentials")


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet():
    if not settings.FERNET_KEY:
        # In local dev mode, store credentials unencrypted (base64 JSON)
        return None
    try:
        from cryptography.fernet import Fernet  # type: ignore
        return Fernet(settings.FERNET_KEY.encode())
    except Exception as e:
        log.warning("credentials.fernet_init_error", error=str(e))
        return None


def _encrypt(data: dict) -> str:
    f = _get_fernet()
    raw = json.dumps(data).encode()
    if f:
        return f.encrypt(raw).decode()
    import base64
    return base64.b64encode(raw).decode()


def _decrypt(enc: str) -> dict:
    f = _get_fernet()
    if f:
        raw = f.decrypt(enc.encode())
    else:
        import base64
        raw = base64.b64decode(enc.encode())
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EbayCredentials(BaseModel):
    user_token: str
    app_id: str = ""
    cert_id: str = ""
    dev_id: str = ""
    is_sandbox: bool = True
    # OAuth: set when user connects via /api/auth/ebay/authorize; used to refresh access token
    refresh_token: str | None = None
    expires_at: float | None = None  # Unix timestamp when user_token expires


class VintedCredentials(BaseModel):
    session_cookies: dict
    is_sandbox: bool = False


class CredentialResponse(BaseModel):
    id: int
    platform: str
    is_sandbox: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@creds_router.get("", response_model=list[CredentialResponse])
async def list_credentials(
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBPlatformCredential).where(DBPlatformCredential.user_id == current_user.user_id)
    )
    return result.scalars().all()


@creds_router.put("/ebay")
async def upsert_ebay_credentials(
    creds: EbayCredentials,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBPlatformCredential).where(
            DBPlatformCredential.user_id == current_user.user_id,
            DBPlatformCredential.platform == "ebay",
        )
    )
    existing = result.scalar_one_or_none()

    encrypted = _encrypt(creds.model_dump())
    if existing:
        existing.credentials_enc = encrypted
        existing.is_sandbox = creds.is_sandbox
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(DBPlatformCredential(
            user_id=current_user.user_id,
            platform="ebay",
            credentials_enc=encrypted,
            is_sandbox=creds.is_sandbox,
        ))
    await db.commit()
    log.info("credentials.ebay_saved", user_id=current_user.user_id)
    return {"ok": True}


@creds_router.put("/vinted")
async def upsert_vinted_credentials(
    creds: VintedCredentials,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBPlatformCredential).where(
            DBPlatformCredential.user_id == current_user.user_id,
            DBPlatformCredential.platform == "vinted",
        )
    )
    existing = result.scalar_one_or_none()

    encrypted = _encrypt(creds.model_dump())
    if existing:
        existing.credentials_enc = encrypted
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(DBPlatformCredential(
            user_id=current_user.user_id,
            platform="vinted",
            credentials_enc=encrypted,
            is_sandbox=False,
        ))
    await db.commit()
    log.info("credentials.vinted_saved", user_id=current_user.user_id)
    return {"ok": True}


@creds_router.delete("/{platform}")
async def delete_credentials(
    platform: str,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBPlatformCredential).where(
            DBPlatformCredential.user_id == current_user.user_id,
            DBPlatformCredential.platform == platform,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    await db.delete(cred)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# eBay: get valid access token (refresh if needed)
# ---------------------------------------------------------------------------

REFRESH_BUFFER_SECONDS = 300  # refresh if expires in less than 5 minutes


async def get_ebay_access_token(user_id: str, db: AsyncSession) -> str | None:
    """
    Load eBay credentials for the user. If they have a refresh_token and the
    access token is expired (or within 5 min), refresh and persist. Return
    the access token to use, or None if no credentials.
    """
    creds_dict = await get_platform_credentials(user_id, "ebay", db)
    if not creds_dict:
        return None
    access = creds_dict.get("user_token")
    refresh = creds_dict.get("refresh_token")
    expires_at = creds_dict.get("expires_at")
    is_sandbox = creds_dict.get("is_sandbox", True)

    if refresh and (expires_at is None or (expires_at - REFRESH_BUFFER_SECONDS) < datetime.now(timezone.utc).timestamp()):
        try:
            from ..ebay_oauth import refresh_access_token
            token_data = await refresh_access_token(refresh, sandbox=is_sandbox)
            new_access = token_data["access_token"]
            new_refresh = token_data.get("refresh_token") or refresh
            new_expires = datetime.now(timezone.utc).timestamp() + token_data.get("expires_in", 7200)
            creds_dict["user_token"] = new_access
            creds_dict["refresh_token"] = new_refresh
            creds_dict["expires_at"] = new_expires
            encrypted = _encrypt(creds_dict)
            result = await db.execute(
                select(DBPlatformCredential).where(
                    DBPlatformCredential.user_id == user_id,
                    DBPlatformCredential.platform == "ebay",
                )
            )
            row = result.scalar_one_or_none()
            if row:
                row.credentials_enc = encrypted
                row.updated_at = datetime.now(timezone.utc)
                await db.commit()
            access = new_access
        except Exception as e:
            log.warning("credentials.ebay_refresh_failed", user_id=user_id, error=str(e))
    return access


# ---------------------------------------------------------------------------
# Helper for agents to load credentials at runtime
# ---------------------------------------------------------------------------

async def get_platform_credentials(user_id: str, platform: str, db: AsyncSession) -> dict | None:
    """Load and decrypt credentials for a given user + platform. Returns None if not set."""
    result = await db.execute(
        select(DBPlatformCredential).where(
            DBPlatformCredential.user_id == user_id,
            DBPlatformCredential.platform == platform,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None
    try:
        return _decrypt(cred.credentials_enc)
    except Exception as e:
        log.warning("credentials.decrypt_error", user_id=user_id, platform=platform, error=str(e))
        return None
