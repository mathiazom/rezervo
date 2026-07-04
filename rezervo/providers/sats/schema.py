from enum import Enum

from pydantic import BaseModel

type SatsLocationIdentifier = int


class SatsClassImage(BaseModel):
    alt: str
    src: str


class SatsClassDetail(BaseModel):
    clubName: str
    duration: int
    durationText: str
    instructor: str
    name: str
    startsAt: str


class SatsClass(BaseModel):
    id: str
    hasWaitingList: bool
    image: SatsClassImage | None = None
    isBooked: bool
    metadata: SatsClassDetail
    text: str | None = ""
    waitingListCount: int


class SatsScheduleResponse(BaseModel):
    classes: list[SatsClass]


class SatsBookingHiddenInput(BaseModel):
    name: str
    value: str


class SatsBooking(BaseModel):
    activityName: str
    bookedCount: int
    capacity: int
    centerName: str
    date: str
    endTime: str
    hiddenInput: list[SatsBookingHiddenInput]
    instructor: str
    startTime: str
    waitingListIndex: int


class SatsBookings(BaseModel):
    trainings: list[SatsBooking]


class SatsDayBookings(BaseModel):
    upcomingTrainings: SatsBookings


class SatsBookingsResponse(BaseModel):
    myUpcomingTraining: list[SatsDayBookings]


class SatsMembershipSettingsProfile(BaseModel):
    data: list[str]


class SatsMembershipSettings(BaseModel):
    profile: SatsMembershipSettingsProfile


class SatsMyPageResponse(BaseModel):
    settings: SatsMembershipSettings


class SatsBookingStatus(Enum):
    BOOKED = "Booked"
    ON_WAITING_LIST = "OnWaitingList"


class SatsBookingResponsePayload(BaseModel):
    status: SatsBookingStatus
    waitingListPosition: int


class SatsBookingResponse(BaseModel):
    payload: SatsBookingResponsePayload
