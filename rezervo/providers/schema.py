from typing import TypeVar

from pydantic import BaseModel

from rezervo.schemas.camel import CamelModel

type LocationIdentifier = str


class CheckInTerminal(CamelModel):
    id: str
    label: str
    has_printer: bool


class BaseLocation(CamelModel):
    identifier: LocationIdentifier
    name: str
    check_in_terminals: list[CheckInTerminal] | None = []


class Location[LocationProviderIdentifier](BaseLocation):
    provider_identifier: LocationProviderIdentifier


type BranchIdentifier = str


class BaseBranch(BaseModel):
    identifier: BranchIdentifier
    name: str


class Branch[LocationProviderIdentifier](BaseBranch):
    locations: list[Location[LocationProviderIdentifier]]


AuthData = TypeVar("AuthData")
