from typing import Optional

from sit_rezervo.schemas.base import OrmBase


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


class UserConfig(OrmBase):
    active: bool = True
    classes: Optional[list[Class]]
    notifications: Optional[Notifications] = None

class PeerConfig(OrmBase):
    peer_name: str
    classes: Optional[list[Class]]
