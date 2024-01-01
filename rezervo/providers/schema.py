from typing import Generic, TypeAlias, TypeVar

from pydantic import BaseModel

LocationIdentifier: TypeAlias = str

LocationProviderIdentifier = TypeVar("LocationProviderIdentifier")


class BaseLocation(BaseModel):
    identifier: LocationIdentifier
    name: str


class Location(BaseLocation, Generic[LocationProviderIdentifier]):
    provider_identifier: LocationProviderIdentifier


BranchIdentifier: TypeAlias = str


class BaseBranch(BaseModel):
    identifier: BranchIdentifier
    name: str


class Branch(BaseBranch, Generic[LocationProviderIdentifier]):
    locations: list[Location[LocationProviderIdentifier]]


AuthResult = TypeVar("AuthResult")
