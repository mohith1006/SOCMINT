"""
Central configuration. Every secret is sourced from the environment
(.env locally, real secrets manager in production) — never hardcoded.
See .env.example for the full list of variables this expects.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "SOCMINT"
    environment: str = "development"

    # --- Database ---
    database_url: str = "postgresql://socmint:socmint@postgres:5432/socmint"

    # --- Auth / JWT ---
    jwt_secret_key: str  # required, no default — must come from .env
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10
    refresh_token_expire_days: int = 7

    # --- Field-level AES-256-GCM encryption key (32 bytes, base64) ---
    field_encryption_key: str  # required, no default

    # --- MFA ---
    mfa_issuer_name: str = "SOCMINT"

    # --- Rate limiting ---
    max_failed_logins_before_flag: int = 5

    # --- Default admin, seeded on first boot if no admin exists yet ---
    default_admin_email: str = "admin@socmint.local"
    default_admin_passcode: str = "ChangeMe#2026!"

    # --- Email (password reset) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@socmint.local"
    password_reset_token_ttl_minutes: int = 30
    frontend_base_url: str = "https://localhost"

    # --- Telegram (telethon) ---
    telegram_api_id: str | None = None
    telegram_api_hash: str | None = None
    telegram_session_name: str = "socmint_ingest"
    # Configurable seed list of public India-focused channels — edit freely,
    # this is intentionally NOT hardcoded into ingestion logic.
    telegram_seed_channels: str = ""  # comma-separated usernames

    # --- Reddit (praw) ---
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "socmint-ingest/0.1"
    reddit_seed_subreddits: str = "india,IndiaSpeaks,indianews"

    # --- X (Twitter) ---
    x_bearer_token: str | None = None

    # --- Supported interface languages (mirrors frontend/src/i18n) ---
    supported_ui_languages: list[str] = ["en", "hi", "te", "ta", "bn"]

    @property
    def telegram_channel_list(self) -> list[str]:
        return [c.strip() for c in self.telegram_seed_channels.split(",") if c.strip()]

    @property
    def reddit_subreddit_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_seed_subreddits.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
