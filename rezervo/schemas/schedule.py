import datetime
import json
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
    room: str | None = None


class RezervoActivity(CamelModel):
    id: str
    name: str
    category: str
    description: str | None = None
    additional_information: str | None = None
    color: str
    image: str | None = None


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
    cancel_text: str | None = None
    total_slots: int | None = None
    available_slots: int | None = None
    waiting_list_count: int | None = None
    user_status: str | None = None
    booking_opens_at: datetime.datetime


class RezervoDay(CamelModel):
    day_name: str
    date: str
    classes: list[RezervoClass]


class RezervoSchedule(CamelModel):
    days: list[RezervoDay]


class BookingResult(CamelModel):
    status: SessionState
    position_in_wait_list: int | None = None


class BaseUserSession(CamelOrmBase):
    chain: ChainIdentifier
    status: SessionState
    position_in_wait_list: int | None = None
    class_data: SessionRezervoClass


class UserSession(BaseUserSession):
    class_id: str
    user_id: UUID


class UserNameSessionStatus(CamelModel):
    is_self: bool
    user_id: UUID
    user_name: str
    status: SessionState
    position_in_wait_list: int | None = None


def session_model_from_user_session(user_session: UserSession):
    return models.Session(
        class_id=user_session.class_id,
        user_id=user_session.user_id,
        status=user_session.status,
        position_in_wait_list=user_session.position_in_wait_list,
        class_data=json.loads(user_session.class_data.json()),
        chain=user_session.chain,
    )
