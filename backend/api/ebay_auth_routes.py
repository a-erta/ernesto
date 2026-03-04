"""
eBay OAuth 2.0 routes — start sign-in and handle callback.
Each user gets their own token; refresh is used automatically when publishing.
"""
from datetime import datetime, timezone

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
    url = get_authorize_url(
        user_id=current_user.user_id,
        sandbox=sandbox,
    )
    from fastapi.responses import RedirectResponse, JSONResponse
    if "application/json" in (request.headers.get("accept") or "").lower():
        return JSONResponse(content={"url": url})
    return RedirectResponse(url=url, status_code=302)


@router.get("/ebay/callback")
async def ebay_callback(
    code: str = Query(..., description="Authorization code from eBay"),
    state: str = Query(..., description="State we sent in authorize"),
    sandbox: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """
    eBay redirects here after the user approves. We exchange the code for
    access_token + refresh_token and store them. user_id comes from signed state.
    """
    user_id = verify_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    token_data = await exchange_code(code=code, sandbox=sandbox)
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

    # Redirect to frontend (e.g. settings or dashboard)
    frontend_origin = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:5173"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{frontend_origin}/?ebay_connected=1", status_code=302)
