from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["backend/.env", ".env"],  # works from project root or backend/
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

    # --- eBay ---
    EBAY_APP_ID: str = ""
    EBAY_CERT_ID: str = ""
    EBAY_DEV_ID: str = ""
    EBAY_USER_TOKEN: str = ""
    EBAY_SANDBOX: bool = True

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
    def use_s3(self) -> bool:
        return bool(self.S3_BUCKET)

    @property
    def use_redis(self) -> bool:
        return bool(self.REDIS_URL)


settings = Settings()
