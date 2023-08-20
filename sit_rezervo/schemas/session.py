from uuid import UUID

from pydantic import BaseModel, Field

from sit_rezervo.models import SessionState
from sit_rezervo.schemas.base import OrmBase
from sit_rezervo.schemas.schedule import SitClass


class UserSession(OrmBase):
    class_id: str
    user_id: UUID
    status: SessionState
    class_data: SitClass


class UserNameSessionStatus(BaseModel):
    is_self: bool
    user_name: str
    status: SessionState


def session_state_from_sit(status: str) -> SessionState:
    match status:
        case "confirmed":
            return SessionState.CONFIRMED
        case "booked":
            return SessionState.BOOKED
        case "waitlist":
            return SessionState.WAITLIST
    return SessionState.UNKNOWN


class SitSession(BaseModel):
    class_field: SitClass = Field(..., alias='class')
    status: str

    class Config:
        allow_population_by_field_name = True
