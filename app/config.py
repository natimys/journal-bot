from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn


class Config(BaseSettings):
    BOT_TOKEN: str
    APP_KEY: str

    MODE: Literal["WHITELIST", "BLACKLIST"] = "WHITELIST"
    LIST: list[int] | None = None

    SECRET_KEY: str

    POSTGRES_URL: PostgresDsn
    REDIS_URL: RedisDsn

    SERVICE_USER_LOGIN: str
    SERVICE_USER_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()
