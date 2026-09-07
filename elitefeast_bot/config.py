from functools import lru_cache
from typing import Optional, Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    admin_telegram_ids: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")
    database_url: str = Field(
        default="sqlite+aiosqlite:///elitefeast_bot.db",
        alias="DATABASE_URL",
    )
    woocommerce_base_url: str = Field(
        default="https://elitefeast.ru",
        alias="WOOCOMMERCE_BASE_URL",
    )
    woocommerce_consumer_key: Optional[str] = Field(
        default=None,
        alias="WOOCOMMERCE_CONSUMER_KEY",
    )
    woocommerce_consumer_secret: Optional[str] = Field(
        default=None,
        alias="WOOCOMMERCE_CONSUMER_SECRET",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
