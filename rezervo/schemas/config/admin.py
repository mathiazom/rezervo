from typing import Optional

from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelOrmBase


class Slack(CamelOrmBase):
    user_id: Optional[str] = None


class Notifications(CamelOrmBase):
    slack: Optional[Slack] = None


class AdminConfig(OrmBase):
    notifications: Optional[Notifications] = None
