from typing import Optional, TypeAlias

from pydantic import BaseModel

SatsLocationIdentifier: TypeAlias = int


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
    image: Optional[SatsClassImage]
    isBooked: bool
    metadata: SatsClassDetail
    text: Optional[str] = ""
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
