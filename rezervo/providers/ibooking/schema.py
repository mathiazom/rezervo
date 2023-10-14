from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pytz import timezone

from rezervo.models import SessionState
from rezervo.schemas.config.user import IntegrationIdentifier
from rezervo.schemas.schedule import RezervoClass, RezervoInstructor, RezervoStudio


class SitInstructor(BaseModel):
    name: str


class SitStudio(BaseModel):
    id: int
    name: str


class SitClass(BaseModel):
    id: int
    name: str
    activityId: int
    from_field: str = Field(..., alias="from")
    to: str
    instructors: list[SitInstructor]
    studio: SitStudio
    userStatus: Optional[str] = None
    bookable: bool
    bookingOpensAt: str

    class Config:
        allow_population_by_field_name = True


class SitDay(BaseModel):
    dayName: str
    date: str
    classes: list[SitClass]


class SitSchedule(BaseModel):
    days: list[SitDay]


class SitSession(BaseModel):
    class_field: SitClass = Field(..., alias="class")
    status: str

    class Config:
        allow_population_by_field_name = True


def session_state_from_sit(status: str) -> SessionState:
    match status:
        case "confirmed":
            return SessionState.CONFIRMED
        case "booked":
            return SessionState.BOOKED
        case "waitlist":
            return SessionState.WAITLIST
    return SessionState.UNKNOWN


def tz_aware_iso_from_sit_date_str(date: str) -> str:
    return timezone("Europe/Oslo").localize(datetime.fromisoformat(date)).isoformat()


def rezervo_class_from_sit_class(sit_class: SitClass) -> RezervoClass:
    return RezervoClass(
        integration=IntegrationIdentifier.SIT,
        id=sit_class.id,
        name=sit_class.name,
        activityId=sit_class.activityId,
        from_field=sit_class.from_field,
        to=sit_class.to,
        instructors=[RezervoInstructor(name=s.name) for s in sit_class.instructors],
        studio=RezervoStudio(
            id=sit_class.studio.id,
            name=sit_class.studio.name,
        ),
        userStatus=sit_class.userStatus,
        bookable=sit_class.bookable,
        bookingOpensAt=tz_aware_iso_from_sit_date_str(sit_class.bookingOpensAt),
    )
