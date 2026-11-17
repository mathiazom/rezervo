import datetime
from typing import Literal
from uuid import UUID

from rezervo.consts import OSLO_TIMEZONE
from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelModel, CamelOrmBase


class HourAndMinute(CamelOrmBase):
    hour: int
    minute: int


class AllowedTimeWindowConfig(CamelOrmBase):
    not_before: HourAndMinute
    not_after: HourAndMinute


class Notifications(CamelOrmBase):
    reminder_hours_before: float | None = None
    reminder_allowed_time_window: AllowedTimeWindowConfig | None = None


class UserPreferences(OrmBase):
    notifications: Notifications | None = None


class UserIdAndNameWithIsSelf(CamelModel):
    is_self: bool
    user_id: UUID
    user_name: str


ChainIdentifier = str


class ClassTime(CamelModel):
    hour: int
    minute: int


class Class(CamelModel):
    activity_id: str
    weekday: int
    location_id: str
    start_time: ClassTime  # TODO: make sure time zones are handled...
    display_name: str | None = None

    def calculate_next_occurrence(
        self, include_today: bool = True
    ) -> datetime.datetime:
        now = datetime.datetime.now().astimezone(OSLO_TIMEZONE)  # TODO: clean this
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
    password: str | None = None


class ChainUser(ChainConfig, ChainUserCredentials, CamelModel):
    user_id: UUID
    auth_data: str | None = None
    auth_verified_at: datetime.datetime | None = None


def config_from_chain_user(user: ChainUser):
    return ChainConfig(**user.model_dump())


class UpdatedChainUserCredsResponse(CamelModel):
    status: Literal["updated"] = "updated"
    profile: ChainUserProfile
