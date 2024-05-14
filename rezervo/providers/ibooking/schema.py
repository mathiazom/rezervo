from datetime import datetime
from typing import Optional, TypeAlias

from pydantic import BaseModel, ConfigDict, Field
from pytz import timezone

from rezervo.models import SessionState
from rezervo.schemas.camel import CamelModel

IBookingLocationIdentifier: TypeAlias = int

IBookingDomain: TypeAlias = str


class IBookingInstructor(CamelModel):
    name: str


class IBookingStudio(CamelModel):
    id: int
    name: str


class IBookingCategory(CamelModel):
    id: str
    name: str


class IBookingWaitlist(CamelModel):
    active: bool
    count: int
    user_position: Optional[int] = None


class IBookingBaseClass(CamelModel):
    id: int
    activity_id: int
    available: Optional[int] = None
    bookable: bool
    capacity: int
    studio: IBookingStudio
    room: Optional[str] = None
    from_field: str = Field(..., alias="from")
    to: str
    name: str
    description: str
    category: IBookingCategory
    image: Optional[str] = None
    color: str
    instructors: list[IBookingInstructor]
    cancel_text: Optional[str] = None
    user_status: Optional[str] = None
    booking_opens_at: str


class IBookingClass(IBookingBaseClass):
    waitlist: IBookingWaitlist


class IBookingDay(CamelModel):
    day_name: str
    date: str
    classes: list[IBookingClass]


class IBookingSchedule(CamelModel):
    days: list[IBookingDay]


class SitSessionClass(IBookingBaseClass):
    wait_list: IBookingWaitlist


class IBookingBookingResponse(CamelModel):
    success: bool
    waitlist: bool
    waitlist_position: int


def ibooking_class_from_sit_session_class(
    sit_session_class: SitSessionClass,
) -> IBookingClass:
    return IBookingClass(
        id=sit_session_class.id,
        activity_id=sit_session_class.activity_id,
        available=sit_session_class.available,
        bookable=sit_session_class.bookable,
        capacity=sit_session_class.capacity,
        studio=sit_session_class.studio,
        room=sit_session_class.room,
        from_field=sit_session_class.from_field,  # type: ignore
        to=sit_session_class.to,
        name=sit_session_class.name,
        description=sit_session_class.description,
        category=sit_session_class.category,
        image=sit_session_class.image,
        color=sit_session_class.color,
        instructors=sit_session_class.instructors,
        cancel_text=sit_session_class.cancel_text,
        user_status=sit_session_class.user_status,
        booking_opens_at=sit_session_class.booking_opens_at,
        waitlist=sit_session_class.wait_list,
    )


class SitSession(BaseModel):
    class_field: SitSessionClass = Field(..., alias="class")
    status: str
    model_config = ConfigDict(populate_by_name=True)


def session_state_from_ibooking(status: str) -> SessionState:
    match status:
        case "confirmed":
            return SessionState.CONFIRMED
        case "booked":
            return SessionState.BOOKED
        case "waitlist":
            return SessionState.WAITLIST
        case "noshow":
            return SessionState.NOSHOW
    return SessionState.UNKNOWN


def tz_aware_iso_from_ibooking_date_str(date: str) -> str:
    return timezone("Europe/Oslo").localize(datetime.fromisoformat(date)).isoformat()
