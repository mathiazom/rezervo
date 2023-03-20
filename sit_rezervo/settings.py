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

    CRON_JOB_COMMENT_PREFIX: str = "sr"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
