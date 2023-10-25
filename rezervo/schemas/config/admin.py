from typing import Optional

from rezervo.schemas.base import OrmBase


class Slack(OrmBase):
    user_id: Optional[str] = None


class Notifications(OrmBase):
    slack: Optional[Slack] = None


class AdminConfig(OrmBase):
    notifications: Optional[Notifications] = None
