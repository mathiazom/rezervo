from typing import Generic, Optional, TypeAlias, TypeVar

from pydantic import BaseModel

from rezervo.schemas.camel import CamelModel

LocationIdentifier: TypeAlias = str

LocationProviderIdentifier = TypeVar("LocationProviderIdentifier")


class CheckInTerminal(CamelModel):
    id: str
    label: str
    has_printer: bool


class BaseLocation(CamelModel):
    identifier: LocationIdentifier
    name: str
    check_in_terminals: Optional[list[CheckInTerminal]] = []


class Location(BaseLocation, Generic[LocationProviderIdentifier]):
    provider_identifier: LocationProviderIdentifier


BranchIdentifier: TypeAlias = str


class BaseBranch(BaseModel):
    identifier: BranchIdentifier
    name: str


class Branch(BaseBranch, Generic[LocationProviderIdentifier]):
    locations: list[Location[LocationProviderIdentifier]]


AuthData = TypeVar("AuthData")
