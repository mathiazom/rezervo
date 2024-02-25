import datetime
import json
from typing import Optional
from uuid import UUID

from rezervo import models
from rezervo.models import SessionState
from rezervo.schemas.camel import CamelModel, CamelOrmBase
from rezervo.schemas.config.user import ChainIdentifier


class RezervoInstructor(CamelModel):
    name: str


class RezervoStudio(CamelModel):
    id: int
    name: str


class RezervoLocation(CamelModel):
    id: str
    studio: str
    room: Optional[str] = None


class RezervoActivity(CamelModel):
    id: str
    name: str
    category: str
    description: Optional[str] = None
    additional_information: Optional[str] = None
    color: str
    image: Optional[str] = None


class BaseRezervoClass(CamelModel):
    id: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    location: RezervoLocation
    activity: RezervoActivity
    instructors: list[RezervoInstructor]


class SessionRezervoClass(BaseRezervoClass):
    pass


class RezervoClass(BaseRezervoClass):
    is_bookable: bool
    is_cancelled: bool
    cancel_text: Optional[str] = None
    total_slots: Optional[int] = None
    available_slots: Optional[int] = None
    waiting_list_count: Optional[int] = None
    user_status: Optional[str] = None
    booking_opens_at: datetime.datetime


class RezervoDay(CamelModel):
    day_name: str
    date: str
    classes: list[RezervoClass]


class RezervoSchedule(CamelModel):
    days: list[RezervoDay]


class BaseUserSession(CamelOrmBase):
    chain: ChainIdentifier
    status: SessionState
    class_data: SessionRezervoClass


class UserSession(BaseUserSession):
    class_id: str
    user_id: UUID


class UserNameSessionStatus(CamelModel):
    is_self: bool
    user_id: UUID
    user_name: str
    status: SessionState


def session_model_from_user_session(user_session: UserSession):
    return models.Session(
        class_id=user_session.class_id,
        user_id=user_session.user_id,
        status=user_session.status,
        class_data=json.loads(user_session.class_data.json()),
        chain=user_session.chain,
    )
