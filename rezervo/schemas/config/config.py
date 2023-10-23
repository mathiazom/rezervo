from typing import Any, Optional
from uuid import UUID

from deepmerge import Merger  # type: ignore[import]
from pydantic import BaseModel, parse_file_as

from rezervo.schemas.base import OrmBase
from rezervo.schemas.config import admin, app, user
from rezervo.schemas.config.admin import AdminConfig
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.user import UserPreferences


class Auth(app.Auth):
    pass


class Booking(app.Booking):
    pass


class Cron(app.Cron):
    pass


class Slack(admin.Slack, app.Slack):
    pass


class PushNotificationSubscriptionKeys(OrmBase):
    p256dh: str
    auth: str


class PushNotificationSubscription(OrmBase):
    endpoint: str
    keys: PushNotificationSubscriptionKeys


class Notifications(user.Notifications, admin.Notifications, app.Notifications):
    slack: Optional[Slack] = None
    push_notification_subscriptions: Optional[list[PushNotificationSubscription]] = None


class ConfigValue(user.UserPreferences, admin.AdminConfig, app.AppConfig):
    auth: Auth
    booking: Booking
    cron: Cron
    notifications: Optional[Notifications] = None


class Config(BaseModel):
    user_id: UUID
    config: ConfigValue


CONFIG_MERGER = Merger(
    # pass in a list of tuple, with the
    # strategies you are looking to apply
    # to each type.
    [
        # (list, ["append"]),
        (dict, ["merge"]),
        # (set, ["union"])
    ],
    # next, choose the fallback strategies,
    # applied to all other types:
    ["override"],
    # finally, choose the strategies in
    # the case where the types conflict:
    ["override"],
)


def config_from_stored(
    user_id: UUID,
    preferences: UserPreferences,
    push_notification_subscriptions: list[PushNotificationSubscription],
    admin_config: AdminConfig,
) -> Config:
    merged_config: dict[str, Any] = {}
    for c in [preferences.dict(), admin_config.dict(), read_app_config().dict()]:
        CONFIG_MERGER.merge(merged_config, c)
    config_value = ConfigValue(**merged_config)
    if config_value.notifications is None:
        config_value.notifications = Notifications()
    config_value.notifications.push_notification_subscriptions = (
        push_notification_subscriptions
    )
    return Config(user_id=user_id, config=config_value)


def read_app_config() -> AppConfig:
    return parse_file_as(app.AppConfig, app.CONFIG_FILE)
