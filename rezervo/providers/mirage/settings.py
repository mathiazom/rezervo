from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MirageSettings(BaseSettings):
    base_url: str = "https://mirage.rezervo.no"
    enabled: bool = True
    model_config = SettingsConfigDict(env_prefix="REZERVO_MIRAGE_", extra="ignore")


@lru_cache
def get_mirage_settings() -> MirageSettings:
    return MirageSettings()
