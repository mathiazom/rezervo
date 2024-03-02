from pydantic import BaseModel

from rezervo.providers.schema import Branch


class ThemeSpecificImages(BaseModel):
    largeLogo: str


class ThemeAgnosticImages(BaseModel):
    smallLogo: str


class ChainProfileImages(BaseModel):
    light: ThemeSpecificImages
    dark: ThemeSpecificImages
    common: ThemeAgnosticImages


class ChainProfile(BaseModel):
    identifier: str
    name: str
    images: ChainProfileImages


class Chain(BaseModel):
    profile: ChainProfile
    branches: list[Branch]
