from pydantic import BaseModel

from rezervo.providers.schema import Branch
from rezervo.schemas.camel import CamelModel


class ThemeSpecificImages(CamelModel):
    large_logo: str


class ThemeAgnosticImages(CamelModel):
    small_logo: str


class ChainProfileImages(BaseModel):
    light: ThemeSpecificImages
    dark: ThemeSpecificImages
    common: ThemeAgnosticImages


class ChainProfile(BaseModel):
    identifier: str
    name: str
    images: ChainProfileImages


class ChainResponse(BaseModel):
    profile: ChainProfile
    branches: list[Branch]
