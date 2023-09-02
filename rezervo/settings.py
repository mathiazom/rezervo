from functools import lru_cache

from pydantic import BaseSettings


@lru_cache()
def get_settings():
    return Settings()


class Settings(BaseSettings):
    IS_DEVELOPMENT: bool = True

    DATABASE_CONNECTION_STRING: str | None = None

    JWT_DOMAIN: str | None = None
    JWT_ALGORITHMS: list[str] | None = None
    JWT_AUDIENCE: str | None = None
    JWT_ISSUER: str | None = None

    CRON_JOB_COMMENT_PREFIX: str = "rezervo"

    AUTH0_MANAGEMENT_API_CLIENT_ID: str | None = None
    AUTH0_MANAGEMENT_API_CLIENT_SECRET: str | None = None

    REZERVO_WEB_API: str | None = None
    WEB_PUSH_PRIVATE_KEY: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
