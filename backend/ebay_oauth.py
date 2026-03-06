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


def make_state(user_id: str, redirect_origin: str = "") -> str:
    """Create a signed state parameter. redirect_origin is sent back in callback for redirect URL."""
    issued = int(time.time())
    origin_b64 = base64.urlsafe_b64encode(redirect_origin.encode()).decode().rstrip("=")
    raw = f"{user_id}.{issued}.{origin_b64}"
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    return _b64(f"{raw}.{sig}".encode())


def verify_state(state: str) -> tuple[str | None, str]:
    """Verify state; return (user_id, redirect_origin). redirect_origin may be empty."""
    try:
        decoded = _b64d(state).decode()
        raw, sig = decoded.rsplit(".", 1)
        expected = hmac.new(
            settings.SECRET_KEY.encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None, ""
        parts = raw.rsplit(".", 2)
        if len(parts) == 3:
            user_id, issued_str, origin_b64 = parts
            pad = 4 - len(origin_b64) % 4
            if pad != 4:
                origin_b64 += "=" * pad
            redirect_origin = base64.urlsafe_b64decode(origin_b64).decode()
        else:
            user_id, issued_str = raw.rsplit(".", 1)
            redirect_origin = ""
        issued = int(issued_str)
        if time.time() - issued > STATE_TTL_SECONDS:
            return None, ""
        return user_id, redirect_origin
    except Exception:
        return None, ""


def get_authorize_url(
    user_id: str,
    redirect_uri: str | None = None,
    scopes: str | None = None,
    sandbox: bool = False,
    redirect_origin: str = "",
) -> str:
    """
    Build the eBay OAuth authorize URL to send the user to.
    redirect_uri must be the RuName from eBay Developer Portal (User Tokens → Redirect URL),
    not the actual callback URL. redirect_origin is the frontend origin to redirect to after OAuth.
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
        "state": make_state(user_id, redirect_origin=(redirect_origin or "").strip()),
    }
    return f"{base}?{urlencode(params)}"


def _get_client_secret(sandbox: bool) -> str:
    """Resolve client secret for token exchange. eBay may use Client Secret or Cert ID (portal-dependent)."""
    if sandbox:
        secret = (settings.EBAY_CLIENT_SECRET or "").strip()
        fallback = (settings.EBAY_CERT_ID or "").strip()
    else:
        secret = (settings.EBAY_PROD_CLIENT_SECRET or "").strip()
        fallback = (settings.EBAY_PROD_CERT_ID or "").strip()
    return secret or fallback


async def exchange_code(
    code: str,
    redirect_uri: str | None = None,
    sandbox: bool = False,
) -> dict:
    """
    Exchange authorization code for access_token and refresh_token.
    Returns dict with access_token, refresh_token, expires_in (seconds).
    Uses EBAY_*_CLIENT_SECRET for Basic auth; if missing, falls back to EBAY_*_CERT_ID (some portals use Cert ID as secret).
    """
    redirect_uri = (redirect_uri or settings.EBAY_OAUTH_REDIRECT_URI or "").strip()
    url = TOKEN_URL_SANDBOX if sandbox else TOKEN_URL_PROD
    client_id = (settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID or "").strip()
    client_secret = _get_client_secret(sandbox)
    if not client_secret:
        raise ValueError(
            "eBay credentials required for OAuth token exchange. Set EBAY_PROD_CLIENT_SECRET or EBAY_PROD_CERT_ID "
            "(or EBAY_CLIENT_SECRET / EBAY_CERT_ID for sandbox). Developer Portal → Application Keys."
        )
    # Avoid accidental whitespace from .env breaking Basic auth
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
            if r.status_code == 401:
                cert_id = ((settings.EBAY_PROD_CERT_ID if not sandbox else settings.EBAY_CERT_ID) or "").strip()
                client_sec_set = bool((settings.EBAY_PROD_CLIENT_SECRET if not sandbox else settings.EBAY_CLIENT_SECRET or "").strip())
                if cert_id and client_sec_set:
                    log.info("ebay_oauth.exchange_code.retry_with_cert_id", sandbox=sandbox)
                    basic_cert = base64.b64encode(f"{client_id}:{cert_id}".encode()).decode()
                    r2 = await client.post(
                        url,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Authorization": f"Basic {basic_cert}",
                        },
                        data={
                            "grant_type": "authorization_code",
                            "code": code,
                            "redirect_uri": redirect_uri,
                        },
                    )
                    if r2.is_success:
                        data = r2.json()
                        log.info("ebay_oauth.exchange_code.success", has_refresh=bool(data.get("refresh_token")), sandbox=sandbox, used_cert_id=True)
                        return {
                            "access_token": data["access_token"],
                            "refresh_token": data.get("refresh_token"),
                            "expires_in": data.get("expires_in", 7200),
                        }
                    try:
                        err_body2 = r2.json()
                    except Exception:
                        err_body2 = r2.text[:500]
                    log.error("ebay_oauth.exchange_code.retry_failed", status=r2.status_code, response=err_body2, sandbox=sandbox)
                    r = r2
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
    Uses _get_client_secret (Client Secret or Cert ID).
    """
    url = TOKEN_URL_SANDBOX if sandbox else TOKEN_URL_PROD
    client_id = settings.EBAY_PROD_APP_ID if not sandbox else settings.EBAY_APP_ID
    client_secret = _get_client_secret(sandbox)
    if not client_secret:
        raise ValueError("EBAY_PROD_CLIENT_SECRET or EBAY_PROD_CERT_ID (or sandbox equivalents) required for token refresh.")
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
