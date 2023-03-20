from typing import Optional

from sit_rezervo.schemas.base import OrmBase


class Slack(OrmBase):
    user_id: str


class Notifications(OrmBase):
    slack: Optional[Slack] = None


class Auth(OrmBase):
    email: str
    password: str


class AdminConfig(OrmBase):
    auth: Auth
    notifications: Optional[Notifications] = None
