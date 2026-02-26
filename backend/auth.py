"""
Authentication module.

In LOCAL_DEV mode (LOCAL_DEV=true in .env): auth is bypassed entirely and a
hardcoded local user is injected. No Cognito setup required.

In production: JWTs are verified against the Cognito User Pool JWKS endpoint.
"""
import httpx
import structlog
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

from .config import settings

log = structlog.get_logger()
bearer_scheme = HTTPBearer(auto_error=False)

LOCAL_USER_ID = "local-user"
LOCAL_USER_EMAIL = "local@ernesto.dev"


class AuthUser(BaseModel):
    user_id: str
    email: str


# ---------------------------------------------------------------------------
# JWKS cache (production only)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_jwks_uri() -> str:
    return (
        f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com"
        f"/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )


_jwks_cache: Optional[dict] = None


async def _fetch_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(_get_jwks_uri())
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    """
    FastAPI dependency that returns the authenticated user.
    In LOCAL_DEV mode, always returns the local user regardless of credentials.
    """
    if settings.LOCAL_DEV:
        return AuthUser(user_id=LOCAL_USER_ID, email=LOCAL_USER_EMAIL)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        jwks = await _fetch_jwks()
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        if not key:
            raise HTTPException(status_code=401, detail="Unknown token key")

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.COGNITO_APP_CLIENT_ID,
        )
        return AuthUser(
            user_id=claims["sub"],
            email=claims.get("email", claims.get("cognito:username", "")),
        )
    except JWTError as e:
        log.warning("auth.jwt_error", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")
