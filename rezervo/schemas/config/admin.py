from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelOrmBase


class Slack(CamelOrmBase):
    user_id: str | None = None


class Notifications(CamelOrmBase):
    slack: Slack | None = None


class AdminConfig(OrmBase):
    notifications: Notifications | None = None
