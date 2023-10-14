from datetime import datetime
from typing import Optional
from uuid import UUID

import pydantic
import requests

from rezervo import models
from rezervo.consts import (
    PLANNED_SESSIONS_NEXT_WHOLE_WEEKS,
    WEEKDAYS,
)
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError
from rezervo.models import SessionState
from rezervo.providers.ibooking.auth import (
    USER_AGENT,
    authenticate_session,
    fetch_public_token,
)
from rezervo.providers.ibooking.consts import (
    MY_SESSIONS_URL,
)
from rezervo.providers.ibooking.schedule import fetch_ibooking_schedule
from rezervo.providers.ibooking.schema import (
    IBookingClass,
    IBookingSchedule,
    IBookingSession,
    rezervo_class_from_ibooking_class,
    session_state_from_ibooking,
)
from rezervo.schemas.config.user import (
    IntegrationConfig,
    IntegrationIdentifier,
    IntegrationUser,
    get_integration_config_from_integration_user,
)
from rezervo.schemas.schedule import UserSession
from rezervo.utils.logging_utils import err
from rezervo.utils.time_utils import total_days_for_next_whole_weeks


def fetch_ibooking_sessions(
    user_id: Optional[UUID] = None,
) -> dict[UUID, list[UserSession]]:
    planned_ibooking_schedule = fetch_ibooking_schedule(
        fetch_public_token(),
        total_days_for_next_whole_weeks(PLANNED_SESSIONS_NEXT_WHOLE_WEEKS),
    )
    with SessionLocal() as db:
        db_ibooking_users_query = db.query(models.IntegrationUser).filter(
            models.IntegrationUser.integration == IntegrationIdentifier.SIT
        )
        if user_id is not None:
            db_ibooking_users_query = db_ibooking_users_query.filter(
                models.IntegrationUser.user_id == user_id
            )
        db_ibooking_users = db_ibooking_users_query.all()
        sessions: dict[UUID, list[UserSession]] = {}
        for db_ibooking_user in db_ibooking_users:
            ibooking_user: IntegrationUser = IntegrationUser.from_orm(db_ibooking_user)
            auth_session = authenticate_session(
                ibooking_user.username, ibooking_user.password
            )
            if isinstance(auth_session, AuthenticationError):
                err.log(
                    f"Authentication failed for '{ibooking_user.username}', abort user sessions pull!"
                )
                continue
            try:
                res = auth_session.get(
                    MY_SESSIONS_URL, headers={"User-Agent": USER_AGENT}
                )
            except requests.exceptions.RequestException as e:
                err.log(
                    f"Failed to retrieve sessions for '{ibooking_user.username}'",
                    e,
                )
                continue
            sessions_json = res.json()
            ibooking_sessions = []
            for s in sessions_json:
                if s["type"] != "groupclass":
                    continue
                ibooking_sessions.append(pydantic.parse_obj_as(IBookingSession, s))
            past_and_imminent_sessions = [
                UserSession(
                    integration=IntegrationIdentifier.SIT,
                    class_id=s.class_field.id,
                    user_id=ibooking_user.user_id,
                    status=session_state_from_ibooking(s.status),
                    class_data=rezervo_class_from_ibooking_class(s.class_field),
                )
                for s in ibooking_sessions
            ]
            planned_sessions = (
                get_user_planned_sessions_from_schedule(
                    get_integration_config_from_integration_user(ibooking_user),
                    planned_ibooking_schedule,
                )
                if planned_ibooking_schedule is not None
                else []
            )
            user_sessions = past_and_imminent_sessions + [
                UserSession(
                    integration=IntegrationIdentifier.SIT,
                    class_id=p.id,
                    user_id=ibooking_user.user_id,
                    status=SessionState.PLANNED,
                    class_data=rezervo_class_from_ibooking_class(p),
                )
                for p in planned_sessions
                if p.id not in [s.class_id for s in past_and_imminent_sessions]
            ]
            sessions[ibooking_user.user_id] = user_sessions
    return sessions


def get_user_planned_sessions_from_schedule(
    integration_config: IntegrationConfig, schedule: IBookingSchedule
) -> list[IBookingClass]:
    if not integration_config.active:
        return []
    classes: list[IBookingClass] = []
    for d in schedule.days:
        for c in d.classes:
            for uc in integration_config.classes:
                if d.dayName != WEEKDAYS[uc.weekday]:
                    continue
                if c.activityId != uc.activity:
                    continue
                start_time = datetime.strptime(c.from_field, "%Y-%m-%d %H:%M:%S")
                time_matches = (
                    start_time.hour == uc.time.hour
                    and start_time.minute == uc.time.minute
                )
                if not time_matches:
                    continue

                opening_time = datetime.fromisoformat(c.bookingOpensAt)
                # check if opening_time is too close to now (if so, it is either already booked or will not be booked)
                if opening_time < datetime.now():
                    continue
                classes.append(c)
    return classes
