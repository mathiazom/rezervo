import datetime
import enum
from typing import Annotated, Literal, Optional, TypeAlias, Union
from uuid import UUID

import pytz
from pydantic import RootModel
from pydantic.fields import Field

from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelModel, CamelOrmBase


class Notifications(CamelOrmBase):
    reminder_hours_before: Optional[float] = None


class UserPreferences(OrmBase):
    notifications: Optional[Notifications] = None


class UserIdAndNameWithIsSelf(CamelModel):
    is_self: bool
    user_id: UUID
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

    def calculate_next_occurrence(
        self, include_today: bool = True
    ) -> datetime.datetime:
        now = datetime.datetime.now().astimezone(
            pytz.timezone("Europe/Oslo")
        )  # TODO: clean this
        days_ahead = self.weekday - now.weekday()
        if days_ahead < 0 or (
            days_ahead == 0
            and not (
                include_today
                and (now.hour, now.minute)
                < (self.start_time.hour, self.start_time.minute)
            )
        ):
            days_ahead += 7
        target_date = now + datetime.timedelta(days=days_ahead)
        return target_date.replace(
            hour=self.start_time.hour, minute=self.start_time.minute
        )


class RecurringBookings(CamelModel):
    recurring_bookings: list[Class]


class BaseChainConfig(RecurringBookings, CamelModel):
    active: bool = True


class ChainConfig(BaseChainConfig, CamelModel):
    chain: ChainIdentifier


class ChainUserUsername(CamelModel):
    username: str


class ChainUserProfile(ChainUserUsername, CamelModel):
    is_auth_verified: bool


class ChainUserCredentials(ChainUserUsername, CamelModel):
    password: Optional[str] = None


class ChainUserTOTP(CamelModel):
    totp: Optional[str] = None


class ChainUserTOTPPayload(CamelModel):
    totp: str


class ChainUser(ChainConfig, ChainUserCredentials, ChainUserTOTP, CamelModel):
    user_id: UUID
    auth_data: Optional[str] = None
    auth_verified_at: Optional[datetime.datetime] = None


def config_from_chain_user(user: ChainUser):
    return ChainConfig(**user.dict())


class UpdatedChainUserCredsResponse(CamelModel):
    status: Literal["updated"] = "updated"
    profile: ChainUserProfile


class InitiatedTOTPFlowResponse(CamelModel):
    status: Literal["initiated_totp_flow"] = "initiated_totp_flow"
    totp_regex: Optional[str] = None


PutChainUserCredsResponse = RootModel[
    Annotated[
        Union[UpdatedChainUserCredsResponse, InitiatedTOTPFlowResponse],
        Field(discriminator="status"),
    ]
]
