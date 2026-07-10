from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MirageSettings(BaseSettings):
    base_url: str = "https://rezervo-mirage.up.railway.app"
    enabled: bool = False
    model_config = SettingsConfigDict(env_prefix="REZERVO_MIRAGE_", extra="ignore")


@lru_cache
def get_mirage_settings() -> MirageSettings:
    return MirageSettings()
