from datetime import datetime
from typing import Optional, TypeAlias

from pydantic import BaseModel, Field
from pytz import timezone

from rezervo.models import SessionState

IBookingLocationIdentifier: TypeAlias = int

IBookingDomain: TypeAlias = str


class IBookingInstructor(BaseModel):
    name: str


class IBookingStudio(BaseModel):
    id: int
    name: str


class IBookingCategory(BaseModel):
    id: str
    name: str


class IBookingWaitlist(BaseModel):
    active: bool
    count: int


class IBookingClass(BaseModel):
    id: int
    activityId: int
    available: Optional[int]
    bookable: bool
    capacity: int
    studio: IBookingStudio
    room: str
    from_field: str = Field(..., alias="from")
    to: str
    name: str
    description: str
    category: IBookingCategory
    image: Optional[str]
    color: str
    instructors: list[IBookingInstructor]
    waitlist: IBookingWaitlist
    cancelText: Optional[str]
    userStatus: Optional[str]
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
