from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from rezervo import models
from rezervo.models import SessionState
from rezervo.schemas.base import OrmBase
from rezervo.schemas.config.user import IntegrationIdentifier


class RezervoInstructor(BaseModel):
    name: str


class RezervoStudio(BaseModel):
    id: int
    name: str


class RezervoClass(BaseModel):
    integration: IntegrationIdentifier
    id: int
    name: str
    activityId: int
    from_field: str = Field(..., alias="from")
    to: str
    instructors: list[RezervoInstructor]
    studio: RezervoStudio
    userStatus: Optional[str] = None
    bookable: bool
    bookingOpensAt: str

    class Config:
        allow_population_by_field_name = True


class RezervoDay(BaseModel):
    dayName: str
    date: str
    classes: list[RezervoClass]


class RezervoSchedule(BaseModel):
    days: list[RezervoDay]


class RezervoSession(BaseModel):
    class_field: RezervoClass = Field(..., alias="class")
    status: str

    class Config:
        allow_population_by_field_name = True


class UserSession(OrmBase):
    integration: IntegrationIdentifier
    class_id: str
    user_id: UUID
    status: SessionState
    class_data: RezervoClass


class UserNameSessionStatus(BaseModel):
    is_self: bool
    user_name: str
    status: SessionState


def session_model_from_user_session(user_session: UserSession):
    data = user_session.class_data.dict()
    data["integration"] = user_session.class_data.integration.value
    return models.Session(
        class_id=user_session.class_id,
        user_id=user_session.user_id,
        status=user_session.status,
        class_data=data,
        integration=user_session.integration,
    )
