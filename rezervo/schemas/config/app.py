from typing import Optional

from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelOrmBase

CONFIG_FILE = "config.json"


class Auth(OrmBase):
    max_attempts: int = 0


class Booking(OrmBase):
    timezone: str
    max_attempts: int = 10
    max_waiting_minutes: int = 60


class Cron(OrmBase):
    precheck_hours: int = 4
    rezervo_dir: str
    python_path: str
    log_path: str
    preparation_minutes: int = 10


class Transfersh(CamelOrmBase):
    url: str


class Slack(CamelOrmBase):
    bot_token: str
    signing_secret: str
    channel_id: str


class Apprise(CamelOrmBase):
    config_file: str


class Notifications(CamelOrmBase):
    host: Optional[str] = None
    transfersh: Transfersh
    slack: Optional[Slack] = None
    apprise: Optional[Apprise] = None


class Content(OrmBase):
    avatars_dir: Optional[str] = None


class AppConfig(OrmBase):
    auth: Auth
    booking: Booking
    cron: Cron
    content: Optional[Content] = None
    notifications: Optional[Notifications] = None
