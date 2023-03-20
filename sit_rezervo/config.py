from dataclasses import dataclass
from io import TextIOWrapper
from typing import Optional

from dataclass_wizard import YAMLWizard


@dataclass
class Auth:
    email: str
    password: str
    max_attempts: int = 3


@dataclass
class Booking:
    timezone: str
    max_attempts: int = 10
    max_waiting_minutes: int = 60


@dataclass
class Cron:
    sit_rezervo_dir: str
    python_path: str
    log_path: str
    preparation_minutes: int = 10
    precheck_hours: Optional[int] = None


@dataclass
class Transfersh:
    url: str


@dataclass
class Slack:
    bot_token: str
    signing_secret: str
    channel_id: str
    user_id: str


@dataclass
class Notifications:
    transfersh: Optional[Transfersh] = None
    slack: Optional[Slack] = None
    reminder_hours_before: Optional[int] = None


@dataclass
class ClassTime:
    hour: int
    minute: int


@dataclass
class Class:
    activity: int
    weekday: int
    studio: int
    time: ClassTime
    display_name: Optional[str] = None


@dataclass
class Config(YAMLWizard):
    auth: Auth
    booking: Booking
    cron: Cron
    classes: list[Class]
    notifications: Optional[Notifications] = None


def config_from_stream(stream: TextIOWrapper) -> Optional[Config]:
    return Config.from_yaml(stream)
