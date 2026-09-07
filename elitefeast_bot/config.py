from functools import lru_cache
import os
from typing import Optional, Set

from dotenv import load_dotenv


load_dotenv(override=False)


def async_database_url(value: str) -> str:
    """Use asyncpg when a standard Render PostgreSQL URL is supplied."""
    if value.startswith("postgresql://"):
        return "postgresql+asyncpg://" + value[len("postgresql://") :]
    if value.startswith("postgres://"):
        return "postgresql+asyncpg://" + value[len("postgres://") :]
    return value


class Settings:
    """Reads Render environment variables, with a local .env fallback for development."""

    def __init__(self) -> None:
        self.telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
        self.admin_telegram_ids = os.getenv("ADMIN_TELEGRAM_IDS", "")
        self.database_url = async_database_url(
            os.getenv("DATABASE_URL", "sqlite+aiosqlite:///elitefeast_bot.db")
        )
        self.woocommerce_base_url = os.getenv("WOOCOMMERCE_BASE_URL", "https://elitefeast.ru")
        self.woocommerce_consumer_key: Optional[str] = os.getenv("WOOCOMMERCE_CONSUMER_KEY")
        self.woocommerce_consumer_secret: Optional[str] = os.getenv("WOOCOMMERCE_CONSUMER_SECRET")

    @property
    def admin_ids(self) -> Set[int]:
        return {
            int(value.strip())
            for value in self.admin_telegram_ids.split(",")
            if value.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


def require_bot_token(settings: Settings) -> str:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the bot.")
    return settings.telegram_bot_token
