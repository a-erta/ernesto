"""
eBay OAuth 2.0 routes — start sign-in and handle callback.
Each user gets their own token; refresh is used automatically when publishing.
"""
import structlog
from datetime import datetime, timezone

log = structlog.get_logger()

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user, AuthUser
from ..ebay_oauth import (
    get_authorize_url,
    verify_state,
    exchange_code,
)
from ..models.db import get_db, DBPlatformCredential
from ..config import settings

# Reuse encryption from credentials
from .credentials_routes import _encrypt

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _mask(s: str, show: int = 6) -> str:
    if not s or len(s) <= show:
        return "***"
    return s[:show] + "..." + s[-2:] if len(s) > show + 2 else s[:show] + "***"


@router.get("/ebay/authorize")
async def ebay_authorize(
    request: Request,
    sandbox: bool = Query(False),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Redirect the user to eBay sign-in. After they approve, eBay redirects back
    to EBAY_OAUTH_REDIRECT_URI with ?code=...&state=...

    When the client sends Accept: application/json (e.g. from fetch with auth),
    returns {"url": "..."} so the frontend can redirect after attaching the token.
    """
    runame = (settings.EBAY_OAUTH_REDIRECT_URI or "").strip()
    client_id = settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID
    log.info(
        "ebay_authorize.start",
        user_id=current_user.user_id,
        sandbox=sandbox,
        runame=runame[:20] + "..." if len(runame) > 20 else runame,
        client_id_mask=_mask(client_id),
    )
    url = get_authorize_url(
        user_id=current_user.user_id,
        sandbox=sandbox,
    )
    log.info(
        "ebay_authorize.redirect",
        auth_host="auth.sandbox.ebay.com" if sandbox else "auth.ebay.com",
        url_len=len(url),
    )
    from fastapi.responses import RedirectResponse, JSONResponse
    if "application/json" in (request.headers.get("accept") or "").lower():
        return JSONResponse(content={"url": url})
    return RedirectResponse(url=url, status_code=302)


@router.get("/ebay/callback")
async def ebay_callback(
    request: Request,
    code: str | None = Query(None, description="Authorization code from eBay"),
    state: str | None = Query(None, description="State we sent in authorize"),
    sandbox: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """
    eBay redirects here after the user approves. We exchange the code for
    access_token + refresh_token and store them. user_id comes from signed state.
    """
    q = dict(request.query_params)
    log.info(
        "ebay_callback.hit",
        query_keys=list(q.keys()),
        has_code=bool(code),
        has_state=bool(state),
        code_len=len(code) if code else 0,
        state_len=len(state) if state else 0,
        sandbox=sandbox,
    )
    if not code or not state:
        log.warning("ebay_callback.missing_params", detail="code and state required from eBay redirect")
        raise HTTPException(
            status_code=400,
            detail="Missing code or state. eBay should redirect here with ?code=...&state=... after the user approves.",
        )

    user_id = verify_state(state)
    if not user_id:
        log.warning("ebay_callback.state_invalid", state_len=len(state))
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    log.info("ebay_callback.state_ok", user_id=user_id)

    try:
        token_data = await exchange_code(code=code, sandbox=sandbox)
    except Exception as e:
        log.error("ebay_callback.exchange_failed", error=str(e), sandbox=sandbox)
        raise
    expires_in = token_data.get("expires_in", 7200)
    expires_at = datetime.now(timezone.utc).timestamp() + expires_in

    creds_payload = {
        "user_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": expires_at,
        "app_id": settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID,
        "cert_id": settings.EBAY_PROD_CERT_ID if not sandbox else settings.EBAY_CERT_ID,
        "dev_id": settings.EBAY_PROD_DEV_ID if not sandbox else settings.EBAY_DEV_ID,
        "is_sandbox": sandbox,
    }

    encrypted = _encrypt(creds_payload)
    result = await db.execute(
        select(DBPlatformCredential).where(
            DBPlatformCredential.user_id == user_id,
            DBPlatformCredential.platform == "ebay",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.credentials_enc = encrypted
        existing.is_sandbox = sandbox
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(DBPlatformCredential(
            user_id=user_id,
            platform="ebay",
            credentials_enc=encrypted,
            is_sandbox=sandbox,
        ))
    await db.commit()

    log.info("ebay_oauth.connected", user_id=user_id, sandbox=sandbox)

    # Redirect to frontend so the app can close the popup and show "eBay connected"
    frontend_origin = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:5173"
    redirect_to = f"{frontend_origin.rstrip('/')}/?ebay_connected=1"
    log.info("ebay_callback.redirect_to_frontend", frontend_origin=frontend_origin, redirect_url=redirect_to)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=redirect_to, status_code=302)
