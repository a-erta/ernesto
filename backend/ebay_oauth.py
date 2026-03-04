"""
eBay OAuth 2.0 — authorize URL, code exchange, and refresh token.
Used so each tenant gets their own token and we can refresh without re-prompting.
"""
import base64
import hashlib
import hmac
import structlog
import time
from urllib.parse import urlencode

import httpx

from .config import settings

log = structlog.get_logger()

# Scopes for listing and fulfillment (all in your granted list).
# sell.negotiation (Best Offer) is not included by default — it often requires an extra license in Production; add via EBAY_OAUTH_SCOPES if granted.
DEFAULT_SCOPES = (
    "https://api.ebay.com/oauth/api_scope "
    "https://api.ebay.com/oauth/api_scope/sell.inventory "
    "https://api.ebay.com/oauth/api_scope/sell.account "
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment"
)

TOKEN_URL_PROD = "https://api.ebay.com/identity/v1/oauth2/token"
TOKEN_URL_SANDBOX = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
AUTH_URL_PROD = "https://auth.ebay.com/oauth2/authorize"
AUTH_URL_SANDBOX = "https://auth.sandbox.ebay.com/oauth2/authorize"


def _b64(s: bytes) -> str:
    return base64.urlsafe_b64encode(s).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


STATE_TTL_SECONDS = 600  # 10 minutes


def make_state(user_id: str) -> str:
    """Create a signed state parameter so we can recover user_id in the callback."""
    issued = int(time.time())
    raw = f"{user_id}.{issued}"
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    return _b64(f"{raw}.{sig}".encode())


def verify_state(state: str) -> str | None:
    """Verify state and return user_id, or None if invalid/expired."""
    try:
        decoded = _b64d(state).decode()
        raw, sig = decoded.rsplit(".", 1)
        expected = hmac.new(
            settings.SECRET_KEY.encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        user_id, issued_str = raw.rsplit(".", 1)
        issued = int(issued_str)
        if time.time() - issued > STATE_TTL_SECONDS:
            return None
        return user_id
    except Exception:
        return None


def get_authorize_url(
    user_id: str,
    redirect_uri: str | None = None,
    scopes: str | None = None,
    sandbox: bool = False,
) -> str:
    """
    Build the eBay OAuth authorize URL to send the user to.
    redirect_uri must be the RuName from eBay Developer Portal (User Tokens → Redirect URL),
    not the actual callback URL. In the portal you set "Auth Accepted URL" to your callback.
    """
    redirect_uri = (redirect_uri or settings.EBAY_OAUTH_REDIRECT_URI or "").strip()
    if not redirect_uri:
        raise ValueError(
            "EBAY_OAUTH_REDIRECT_URI must be set to your eBay RuName (from Developer Portal → "
            "User Tokens → Get a Token → Redirect URL). It is not your callback URL."
        )
    scopes = scopes or getattr(settings, "EBAY_OAUTH_SCOPES", None) or DEFAULT_SCOPES
    client_id = settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID
    if not (client_id and client_id.strip()):
        raise ValueError("eBay App ID missing. Set EBAY_PROD_APP_ID (or EBAY_APP_ID for sandbox).")
    base = AUTH_URL_SANDBOX if sandbox else AUTH_URL_PROD
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scopes.strip(),
        "state": make_state(user_id),
    }
    return f"{base}?{urlencode(params)}"


async def exchange_code(
    code: str,
    redirect_uri: str | None = None,
    sandbox: bool = False,
) -> dict:
    """
    Exchange authorization code for access_token and refresh_token.
    Returns dict with access_token, refresh_token, expires_in (seconds).
    """
    redirect_uri = (redirect_uri or settings.EBAY_OAUTH_REDIRECT_URI or "").strip()
    url = TOKEN_URL_SANDBOX if sandbox else TOKEN_URL_PROD
    client_id = settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID
    client_secret = settings.EBAY_PROD_CLIENT_SECRET if not sandbox else settings.EBAY_CLIENT_SECRET
    if not (client_secret and client_secret.strip()):
        raise ValueError(
            "eBay Client Secret required for OAuth token exchange. Set EBAY_PROD_CLIENT_SECRET (or EBAY_CLIENT_SECRET for sandbox). "
            "Find it in Developer Portal → Application Keys → (Production) → Client Secret."
        )
    raw = f"{client_id}:{client_secret}"
    basic = base64.b64encode(raw.encode()).decode()

    log.info(
        "ebay_oauth.exchange_code",
        token_url=url,
        redirect_uri_len=len(redirect_uri),
        code_len=len(code),
        sandbox=sandbox,
    )
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
    if not r.is_success:
        try:
            err_body = r.json()
        except Exception:
            err_body = r.text[:500]
        log.error(
            "ebay_oauth.exchange_code.failed",
            status=r.status_code,
            response=err_body,
            sandbox=sandbox,
        )
    r.raise_for_status()
    data = r.json()
    log.info("ebay_oauth.exchange_code.success", has_refresh=bool(data.get("refresh_token")), sandbox=sandbox)
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in", 7200),
    }


async def refresh_access_token(
    refresh_token: str,
    sandbox: bool = False,
) -> dict:
    """
    Get a new access_token using refresh_token.
    Returns dict with access_token, expires_in; refresh_token may be rotated.
    """
    url = TOKEN_URL_SANDBOX if sandbox else TOKEN_URL_PROD
    client_id = settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID
    client_secret = settings.EBAY_PROD_CLIENT_SECRET if not sandbox else settings.EBAY_CLIENT_SECRET
    if not (client_secret and client_secret.strip()):
        raise ValueError("EBAY_PROD_CLIENT_SECRET (or EBAY_CLIENT_SECRET for sandbox) required for token refresh.")
    raw = f"{client_id}:{client_secret}"
    basic = base64.b64encode(raw.encode()).decode()

    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
    r.raise_for_status()
    data = r.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),  # eBay may return new one
        "expires_in": data.get("expires_in", 7200),
    }
