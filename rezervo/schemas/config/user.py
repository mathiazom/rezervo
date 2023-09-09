import enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from rezervo.schemas.base import OrmBase


class Notifications(OrmBase):
    reminder_hours_before: Optional[float] = None


class ClassTime(OrmBase):
    hour: int
    minute: int


class Class(OrmBase):
    activity: int
    weekday: int
    studio: int
    time: ClassTime
    display_name: Optional[str] = None


class UserPreferences(OrmBase):
    notifications: Optional[Notifications] = None


class UserNameWithIsSelf(BaseModel):
    is_self: bool
    user_name: str


class IntegrationIdentifier(enum.Enum):
    SIT = "sit"
    FSC = "fsc"


class BaseIntegrationConfig(OrmBase):
    active: bool = True
    classes: list[Class]


class IntegrationConfig(BaseIntegrationConfig):
    integration: IntegrationIdentifier


class IntegrationUserProfile(OrmBase):
    username: str


class IntegrationUserCredentials(IntegrationUserProfile):
    password: str


class IntegrationUser(IntegrationConfig, IntegrationUserCredentials):
    user_id: UUID
    auth_token: Optional[str] = None


def get_integration_config_from_integration_user(integration_user: IntegrationUser):
    return IntegrationConfig(
        integration=integration_user.integration,
        active=integration_user.active,
        classes=integration_user.classes,
    )
