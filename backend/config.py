from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Local dev; then Render Secret File (Dashboard → Secret Files) mounted at /etc/secrets/
        env_file=["backend/.env", ".env", "/etc/secrets/.env"],
        extra="ignore",
    )

    # --- Core ---
    OPENAI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./ernesto.db"
    SECRET_KEY: str = "dev-secret-key"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8081"

    # --- Local dev mode (bypasses auth, S3, Redis) ---
    # Set to false in production
    LOCAL_DEV: bool = True

    # --- Auth — Supabase (production only, ignored when LOCAL_DEV=true) ---
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""  # Settings > API > JWT Secret in Supabase dashboard
    SUPABASE_ANON_KEY: str = ""    # Settings > API > anon/public key (used by frontend)

    # --- Storage (S3 — production) ---
    S3_BUCKET: str = ""
    CLOUDFRONT_DOMAIN: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # --- Real-time (Redis — production) ---
    REDIS_URL: str = ""

    # --- Encryption (for platform credentials at rest) ---
    FERNET_KEY: str = ""

    # --- eBay sandbox ---
    EBAY_APP_ID: str = ""
    EBAY_CERT_ID: str = ""
    EBAY_DEV_ID: str = ""
    EBAY_USER_TOKEN: str = ""
    EBAY_SANDBOX: bool = True

    # --- eBay production ---
    EBAY_PROD_APP_ID: str = ""
    EBAY_PROD_CERT_ID: str = ""
    EBAY_PROD_DEV_ID: str = ""
    EBAY_PROD_USER_TOKEN: str = ""

    # --- eBay marketplace (EBAY_US, EBAY_IT, EBAY_GB, EBAY_DE, EBAY_FR, EBAY_ES, ...) ---
    EBAY_MARKETPLACE_ID: str = "EBAY_US"

    # --- eBay OAuth (for per-user tokens; optional) ---
    # Must match "Your auth accepted URL" in eBay Developer Portal → Get a Token → OAuth.
    EBAY_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/ebay/callback"
    # Space-separated OAuth scopes, e.g. "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory"
    EBAY_OAUTH_SCOPES: str = "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/sell.fulfillment https://api.ebay.com/oauth/api_scope/sell.negotiation"

    # --- eBay listing policies (set after running test_ebay.py --prod) ---
    # Policies are marketplace-specific — run test_ebay.py for each marketplace you use.
    EBAY_FULFILLMENT_POLICY_ID: str = ""
    EBAY_PAYMENT_POLICY_ID: str = ""
    EBAY_RETURN_POLICY_ID: str = ""
    EBAY_MERCHANT_LOCATION_KEY: str = ""

    # --- Telegram (optional) ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def use_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def database_url_async(self) -> str:
        """DATABASE_URL with async driver. Render gives postgresql://; we need postgresql+asyncpg://."""
        u = self.DATABASE_URL
        if u.startswith("postgresql://") and "+asyncpg" not in u:
            return "postgresql+asyncpg://" + u.split("://", 1)[1]
        return u

    @property
    def use_s3(self) -> bool:
        return bool(self.S3_BUCKET)

    @property
    def use_redis(self) -> bool:
        return bool(self.REDIS_URL)


settings = Settings()
