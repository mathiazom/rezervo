from functools import lru_cache

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


@lru_cache()
def get_settings():
    return Settings()


class Settings(BaseSettings):
    IS_DEVELOPMENT: bool = True

    DATABASE_CONNECTION_STRING: str | None = None

    JWT_ALGORITHMS: list[str] | None = None
    JWT_AUDIENCE: str | None = None
    JWT_ISSUER: str | None = None
    JWT_PUBLIC_KEY: str | None = None

    def decoded_jwt_public_key(self):
        return self.JWT_PUBLIC_KEY.replace("\\n", "\n").encode()

    CRON_JOB_COMMENT_PREFIX: str = "rezervo"

    WEB_PUSH_EMAIL: str | None = None
    WEB_PUSH_PRIVATE_KEY: str | None = None
    model_config = SettingsConfigDict(
        env_file=find_dotenv(".env"), env_file_encoding="utf-8"
    )
