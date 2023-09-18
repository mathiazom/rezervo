from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import pydantic
import requests

from rezervo import models
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError
from rezervo.integrations.fsc.auth import authenticate_session
from rezervo.integrations.fsc.booking import booking_url
from rezervo.integrations.fsc.schedule import fetch_fsc_schedule
from rezervo.integrations.fsc.schema import (
    BookingData,
    BookingsResponse,
    FscClass,
    rezervo_class_from_fsc_class,
    session_state_from_fsc,
)
from rezervo.models import SessionState
from rezervo.schemas.config.user import (
    IntegrationConfig,
    IntegrationIdentifier,
    IntegrationUser,
    get_integration_config_from_integration_user,
)
from rezervo.schemas.schedule import UserSession
from rezervo.utils.logging_utils import err


def fetch_fsc_sessions(user_id: Optional[UUID] = None) -> dict[UUID, list[UserSession]]:
    fsc_schedule = fetch_fsc_schedule()
    with SessionLocal() as db:
        db_fsc_users_query = db.query(models.IntegrationUser).filter(
            models.IntegrationUser.integration == IntegrationIdentifier.FSC
        )
        if user_id is not None:
            db_fsc_users_query = db_fsc_users_query.filter(
                models.IntegrationUser.user_id == user_id
            )
        db_fsc_users = db_fsc_users_query.all()
        sessions: dict[UUID, list[UserSession]] = {}
        for db_fsc_user in db_fsc_users:
            fsc_user: IntegrationUser = IntegrationUser.from_orm(db_fsc_user)
            auth_session = authenticate_session(fsc_user.username, fsc_user.password)
            if isinstance(auth_session, AuthenticationError):
                err.log(
                    f"Authentication failed for '{fsc_user.username}', abort user sessions pull!"
                )
                continue
            try:
                res = auth_session.get(booking_url(auth_session))
            except requests.exceptions.RequestException as e:
                err.log(
                    f"Failed to retrieve sessions for '{fsc_user.username}'",
                    e,
                )
                continue
            bookings_response: BookingsResponse = res.json()
            fsc_sessions = []
            if "data" in bookings_response:
                for s in bookings_response["data"]:
                    fsc_sessions.append(pydantic.parse_obj_as(BookingData, s))
            past_and_imminent_sessions = [
                UserSession(
                    integration=IntegrationIdentifier.FSC,
                    class_id=s.groupActivity.id,
                    user_id=fsc_user.user_id,
                    status=session_state_from_fsc(s.type),
                    class_data=rezervo_class_from_fsc_class(
                        next(
                            filter(lambda c: c.id == s.groupActivity.id, fsc_schedule),
                            None,
                        )
                    ),
                )
                for s in fsc_sessions
            ]
            planned_sessions = (
                get_user_planned_sessions_from_schedule(
                    get_integration_config_from_integration_user(fsc_user),
                    fsc_schedule,
                )
                if fsc_schedule is not None
                else []
            )
            user_sessions = past_and_imminent_sessions + [
                UserSession(
                    integration=IntegrationIdentifier.FSC,
                    class_id=p.id,
                    user_id=fsc_user.user_id,
                    status=SessionState.PLANNED,
                    class_data=rezervo_class_from_fsc_class(p),
                )
                for p in planned_sessions
                if p.id not in [s.class_id for s in past_and_imminent_sessions]
            ]
            sessions[fsc_user.user_id] = user_sessions
    return sessions


def get_user_planned_sessions_from_schedule(
    integration_config: IntegrationConfig, schedule: List[FscClass]
) -> list[FscClass]:
    if not integration_config.active:
        return []
    classes: list[FscClass] = []
    for c in schedule:
        for uc in integration_config.classes:
            if c.groupActivityProduct.id != uc.activity:
                continue
            start_time = datetime.fromisoformat(c.duration.start.replace("Z", "")[:-4])
            time_matches = (
                start_time.hour == uc.time.hour and start_time.minute == uc.time.minute
            )
            if not time_matches:
                continue
            # check if start time is too close to now (if so, it is either already booked or will not be booked)
            if start_time < datetime.now() + timedelta(
                days=6  # TODO: due to be changed by other PR
            ):
                continue
            classes.append(c)
    return classes
