from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pytz import timezone

from rezervo.models import SessionState
from rezervo.schemas.config.user import IntegrationIdentifier
from rezervo.schemas.schedule import RezervoClass, RezervoInstructor, RezervoStudio


class IBookingInstructor(BaseModel):
    name: str


class IBookingStudio(BaseModel):
    id: int
    name: str


class IBookingClass(BaseModel):
    id: int
    name: str
    activityId: int
    from_field: str = Field(..., alias="from")
    to: str
    instructors: list[IBookingInstructor]
    studio: IBookingStudio
    userStatus: Optional[str] = None
    bookable: bool
    bookingOpensAt: str

    class Config:
        allow_population_by_field_name = True


class IBookingDay(BaseModel):
    dayName: str
    date: str
    classes: list[IBookingClass]


class IBookingSchedule(BaseModel):
    days: list[IBookingDay]


class IBookingSession(BaseModel):
    class_field: IBookingClass = Field(..., alias="class")
    status: str

    class Config:
        allow_population_by_field_name = True


def session_state_from_ibooking(status: str) -> SessionState:
    match status:
        case "confirmed":
            return SessionState.CONFIRMED
        case "booked":
            return SessionState.BOOKED
        case "waitlist":
            return SessionState.WAITLIST
    return SessionState.UNKNOWN


def tz_aware_iso_from_ibooking_date_str(date: str) -> str:
    return timezone("Europe/Oslo").localize(datetime.fromisoformat(date)).isoformat()


def rezervo_class_from_ibooking_class(ibooking_class: IBookingClass) -> RezervoClass:
    return RezervoClass(
        integration=IntegrationIdentifier.SIT,
        id=ibooking_class.id,
        name=ibooking_class.name,
        activityId=ibooking_class.activityId,
        from_field=ibooking_class.from_field,
        to=ibooking_class.to,
        instructors=[
            RezervoInstructor(name=s.name) for s in ibooking_class.instructors
        ],
        studio=RezervoStudio(
            id=ibooking_class.studio.id,
            name=ibooking_class.studio.name,
        ),
        userStatus=ibooking_class.userStatus,
        bookable=ibooking_class.bookable,
        bookingOpensAt=tz_aware_iso_from_ibooking_date_str(
            ibooking_class.bookingOpensAt
        ),
    )
