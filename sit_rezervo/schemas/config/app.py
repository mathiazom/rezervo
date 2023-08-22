from typing import Optional

from sit_rezervo.schemas.base import OrmBase

CONFIG_FILE = "config.json"


class Auth(OrmBase):
    max_attempts: int = 0


class Booking(OrmBase):
    timezone: str
    max_attempts: int = 10
    max_waiting_minutes: int = 60


class Cron(OrmBase):
    precheck_hours: int = 4
    sit_rezervo_dir: str
    python_path: str
    log_path: str
    preparation_minutes: int = 10


class Transfersh(OrmBase):
    url: str


class Slack(OrmBase):
    bot_token: str
    signing_secret: str
    channel_id: str


class Notifications(OrmBase):
    host: Optional[str] = None
    transfersh: Transfersh
    slack: Optional[Slack] = None


class AppConfig(OrmBase):
    auth: Auth
    booking: Booking
    cron: Cron
    notifications: Optional[Notifications] = None
