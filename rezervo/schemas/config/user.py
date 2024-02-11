import enum
from datetime import datetime
from typing import Optional, TypeAlias
from uuid import UUID

from pydantic import BaseModel

from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelModel


class Notifications(OrmBase):
    reminder_hours_before: Optional[float] = None


class UserPreferences(OrmBase):
    notifications: Optional[Notifications] = None


class UserNameWithIsSelf(BaseModel):
    is_self: bool
    user_name: str


ChainIdentifier: TypeAlias = str


class ProviderIdentifier(enum.Enum):
    BRP = "brpsystems"
    IBOOKING = "ibooking"


class ClassTime(CamelModel):
    hour: int
    minute: int


class Class(CamelModel):
    activity_id: str
    weekday: int
    location_id: str
    start_time: ClassTime  # TODO: make sure time zones are handled...
    display_name: Optional[str] = None


class RecurringBookings(CamelModel):
    recurring_bookings: list[Class]


class BaseChainConfig(RecurringBookings, CamelModel):
    active: bool = True


class ChainConfig(BaseChainConfig, CamelModel):
    chain: ChainIdentifier


class ChainUserProfile(CamelModel):
    username: str


class ChainUserCredentials(ChainUserProfile, CamelModel):
    password: str


class ChainUser(ChainConfig, ChainUserCredentials, CamelModel):
    user_id: UUID
    auth_token: Optional[str] = None
    auth_lockout: Optional[datetime] = None


def config_from_chain_user(user: ChainUser):
    return ChainConfig(**user.dict())
