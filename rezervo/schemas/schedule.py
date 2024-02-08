import datetime
import json
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from rezervo import models
from rezervo.models import SessionState
from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelModel
from rezervo.schemas.config.user import ChainIdentifier


class RezervoInstructor(CamelModel):
    name: str


class RezervoStudio(CamelModel):
    id: int
    name: str


class RezervoLocation(CamelModel):
    id: str
    studio: str
    room: str


class RezervoActivity(CamelModel):
    id: str
    name: str
    category: str
    description: str
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
    total_slots: Optional[int]
    available_slots: Optional[int]
    waiting_list_count: Optional[int]
    user_status: Optional[str]
    booking_opens_at: datetime.datetime


class RezervoDay(CamelModel):
    day_name: str
    date: str
    classes: list[RezervoClass]


class RezervoSchedule(CamelModel):
    days: list[RezervoDay]


class UserSession(OrmBase):
    chain: ChainIdentifier
    class_id: str
    user_id: UUID
    status: SessionState
    class_data: SessionRezervoClass


class UserNameSessionStatus(BaseModel):
    is_self: bool
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
