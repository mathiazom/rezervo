from typing import Optional

from pydantic import BaseModel, Field


class SitInstructor(BaseModel):
    name: str


class SitStudio(BaseModel):
    id: int
    name: str


class SitClass(BaseModel):
    id: int
    name: str
    activityId: int
    from_field: str = Field(..., alias='from')
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
