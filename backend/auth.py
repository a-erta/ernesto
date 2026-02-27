"""
Authentication module.

LOCAL_DEV=true  → auth bypassed, hardcoded local user injected (no setup needed).
LOCAL_DEV=false → Supabase JWT verified via the JWKS discovery endpoint.

Supabase now uses asymmetric signing keys (ES256/RS256) by default for all new
projects. The public keys are published at:
  https://<project>.supabase.co/auth/v1/.well-known/jwks.json

We fetch and cache those keys to verify tokens locally — no round-trip to
Supabase Auth on every request.

If your project still uses the legacy HS256 JWT secret (older projects that
haven't migrated), set SUPABASE_JWT_SECRET in your .env and we fall back to
symmetric verification automatically.
"""
import httpx
import structlog
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
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
# JWKS cache (asymmetric keys — new Supabase projects)
# ---------------------------------------------------------------------------

_jwks_cache: Optional[dict] = None


async def _fetch_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def _find_key(jwks: dict, kid: Optional[str]) -> Optional[dict]:
    """Return the matching JWK from the key set."""
    keys = jwks.get("keys", [])
    if not keys:
        return None
    if kid:
        match = next((k for k in keys if k.get("kid") == kid), None)
        if match:
            return match
    # Fall back to first key if no kid or no match
    return keys[0]


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    """
    FastAPI dependency — returns the authenticated user.
    In LOCAL_DEV mode, always returns the local user with no token required.
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

    # --- Try asymmetric JWKS verification first (new Supabase projects) ---
    if settings.SUPABASE_URL:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            alg = header.get("alg", "ES256")

            jwks = await _fetch_jwks()
            key_data = _find_key(jwks, kid)

            if key_data:
                public_key = jwk.construct(key_data)
                claims = jwt.decode(
                    token,
                    public_key,
                    algorithms=[alg],
                    options={"verify_aud": False},
                )
                user_id = claims.get("sub", "")
                email = claims.get("email", "")
                if not user_id:
                    raise HTTPException(status_code=401, detail="Invalid token: missing sub")
                return AuthUser(user_id=user_id, email=email)
        except JWTError as e:
            # If JWKS fails and we have a legacy secret, fall through to HS256
            if not settings.SUPABASE_JWT_SECRET:
                log.warning("auth.jwks_error", error=str(e))
                raise HTTPException(status_code=401, detail="Invalid token")
            log.debug("auth.jwks_failed_trying_legacy", error=str(e))

    # --- Fall back to legacy HS256 JWT secret (older Supabase projects) ---
    if settings.SUPABASE_JWT_SECRET:
        try:
            claims = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = claims.get("sub", "")
            email = claims.get("email", "")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token: missing sub")
            return AuthUser(user_id=user_id, email=email)
        except JWTError as e:
            log.warning("auth.jwt_error", error=str(e))
            raise HTTPException(status_code=401, detail="Invalid token")

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Auth misconfigured: set SUPABASE_URL or SUPABASE_JWT_SECRET",
    )
