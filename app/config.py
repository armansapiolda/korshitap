"""Configuration settings for KORSHI TAP."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = "placeholder_token"

    # AI Configuration
    # Options: "gemini", "vertex", "mock"
    AI_PROVIDER: str = "mock"
    AI_MODEL: str = "gemini-2.5-flash"
    
    # Google AI Studio API Key
    GEMINI_API_KEY: Optional[str] = None

    # Google Cloud Vertex AI settings
    USE_VERTEX_AI: bool = False
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///korshi_tap.db"

    # Admin Web Panel
    ADMIN_HOST: str = "127.0.0.1"
    ADMIN_PORT: int = 8000
    ADMIN_SECRET_KEY: str = "korshi-tap-secret-key-change-in-production"

    # Freshness Check (days before prompt)
    LISTING_FRESHNESS_DAYS: int = 7

    # Public HTTPS URL for Telegram WebApp (e.g. from tunnel or domain)
    PUBLIC_WEB_URL: Optional[str] = None


settings = Settings()


def get_public_map_url() -> str:
    """Returns the HTTPS URL for Telegram Mini App / WebApp map."""
    from pathlib import Path

    if settings.PUBLIC_WEB_URL:
        return f"{settings.PUBLIC_WEB_URL.rstrip('/')}/map"

    try:
        url_file = Path(__file__).resolve().parent / "public_url.txt"
        if url_file.exists():
            val = url_file.read_text(encoding="utf-8").strip()
            if val.startswith("http"):
                return f"{val.rstrip('/')}/map"
    except Exception:
        pass

    return f"http://{settings.ADMIN_HOST}:{settings.ADMIN_PORT}/map"
