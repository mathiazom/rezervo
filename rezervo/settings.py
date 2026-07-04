from functools import lru_cache

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


@lru_cache
def get_settings():
    # pydantic-settings populates fields from the environment / env file, so no
    # constructor arguments are required (not yet understood by ty).
    return Settings()  # ty: ignore[missing-argument]


class Settings(BaseSettings):
    FUSIONAUTH_API_KEY: str
    FUSIONAUTH_DEFAULT_TENANT_ID: str

    model_config = SettingsConfigDict(
        env_file=[find_dotenv("fusionauth.env")],
        env_file_encoding="utf-8",
        extra="ignore",
    )
