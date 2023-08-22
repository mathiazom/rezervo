from typing import Optional
from uuid import UUID

from deepmerge import Merger
from pydantic import parse_file_as

from sit_rezervo.schemas.base import OrmBase
from sit_rezervo.schemas.config import admin, app, user, stored
from sit_rezervo.schemas.config.app import AppConfig


class Auth(admin.Auth, app.Auth):
    pass


class Booking(app.Booking):
    pass


class Cron(app.Cron):
    pass


class Slack(admin.Slack, app.Slack):
    pass


class Notifications(user.Notifications, admin.Notifications, app.Notifications):
    slack: Optional[Slack] = None


class Class(user.Class):
    pass


class ConfigValue(user.UserConfig, admin.AdminConfig, app.AppConfig):
    active: bool
    auth: Auth
    booking: Booking
    cron: Cron
    notifications: Optional[Notifications] = None
    classes: Optional[list[Class]]


class Config(OrmBase):
    id: UUID
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


def config_from_stored(s: stored.StoredConfig) -> Config:
    merged_config = {}
    for c in [s.config.dict(), s.admin_config.dict(), read_app_config().dict()]:
        CONFIG_MERGER.merge(merged_config, c)
    return Config(id=s.id, user_id=s.user_id, config=ConfigValue(**merged_config))


def read_app_config() -> AppConfig:
    return parse_file_as(app.AppConfig, app.CONFIG_FILE)
