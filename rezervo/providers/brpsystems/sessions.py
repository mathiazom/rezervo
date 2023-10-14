from datetime import datetime
from typing import List, Optional
from uuid import UUID

import pydantic
import pytz
import requests

from rezervo import models
from rezervo.consts import PLANNED_SESSIONS_NEXT_WHOLE_WEEKS
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError
from rezervo.models import SessionState
from rezervo.providers.brpsystems.auth import authenticate
from rezervo.providers.brpsystems.booking import booking_url
from rezervo.providers.brpsystems.schedule import fetch_brp_schedule
from rezervo.providers.brpsystems.schema import (
    BookingData,
    BrpClass,
    BrpSubdomain,
    rezervo_class_from_brp_class,
    session_state_from_brp,
    tz_aware_iso_from_brp_date_str,
)
from rezervo.schemas.config.user import (
    IntegrationConfig,
    IntegrationUser,
    get_integration_config_from_integration_user,
)
from rezervo.schemas.schedule import UserSession
from rezervo.utils.logging_utils import err
from rezervo.utils.time_utils import total_days_for_next_whole_weeks


def fetch_brp_sessions(
    subdomain: BrpSubdomain, business_unit: int, user_id: Optional[UUID] = None
) -> dict[UUID, list[UserSession]]:
    brp_schedule = fetch_brp_schedule(
        subdomain,
        business_unit,
        days=total_days_for_next_whole_weeks(PLANNED_SESSIONS_NEXT_WHOLE_WEEKS),
    )
    with SessionLocal() as db:
        db_brp_users_query = db.query(models.IntegrationUser).filter(
            models.IntegrationUser.integration == subdomain
        )
        if user_id is not None:
            db_brp_users_query = db_brp_users_query.filter(
                models.IntegrationUser.user_id == user_id
            )
        db_brp_users = db_brp_users_query.all()
        sessions: dict[UUID, list[UserSession]] = {}
        for db_brp_user in db_brp_users:
            brp_user: IntegrationUser = IntegrationUser.from_orm(db_brp_user)
            auth_result = authenticate(subdomain, brp_user.username, brp_user.password)
            if isinstance(auth_result, AuthenticationError):
                err.log(
                    f"Authentication failed for '{brp_user.username}', abort user sessions pull!"
                )
                continue
            try:
                res = requests.get(
                    booking_url(subdomain, auth_result),
                    headers={
                        "Authorization": f"Bearer {auth_result['access_token']}",
                    },
                )
            except requests.exceptions.RequestException as e:
                err.log(
                    f"Failed to retrieve sessions for '{brp_user.username}'",
                    e,
                )
                continue
            bookings_response: List[BookingData] = res.json()
            brp_sessions = []
            for s in bookings_response:
                brp_sessions.append(pydantic.parse_obj_as(BookingData, s))
            past_and_imminent_sessions = []
            for s in brp_sessions:
                brp_class = next(
                    filter(lambda c: c.id == s.groupActivity.id, brp_schedule),
                    None,
                )
                if brp_class is None:
                    continue
                past_and_imminent_sessions.append(
                    UserSession(
                        integration=subdomain,
                        class_id=s.groupActivity.id,
                        user_id=brp_user.user_id,
                        status=session_state_from_brp(s.type),
                        class_data=rezervo_class_from_brp_class(subdomain, brp_class),
                    )
                )
            planned_sessions = (
                get_user_planned_sessions_from_schedule(
                    get_integration_config_from_integration_user(brp_user),
                    brp_schedule,
                )
                if brp_schedule is not None
                else []
            )
            user_sessions = past_and_imminent_sessions + [
                UserSession(
                    integration=subdomain,
                    class_id=p.id,
                    user_id=brp_user.user_id,
                    status=SessionState.PLANNED,
                    class_data=rezervo_class_from_brp_class(subdomain, p),
                )
                for p in planned_sessions
                if p.id not in [s.class_id for s in past_and_imminent_sessions]
            ]
            sessions[brp_user.user_id] = user_sessions
    return sessions


def get_user_planned_sessions_from_schedule(
    integration_config: IntegrationConfig, schedule: List[BrpClass]
) -> list[BrpClass]:
    if not integration_config.active:
        return []
    classes: list[BrpClass] = []
    for c in schedule:
        for uc in integration_config.classes:
            if c.groupActivityProduct.id != uc.activity:
                continue
            start_time = datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(c.duration.start)
            ).astimezone(pytz.timezone("Europe/Oslo"))
            time_matches = (
                start_time.hour == uc.time.hour and start_time.minute == uc.time.minute
            )
            if not time_matches:
                continue
            opening_time = datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(c.bookableEarliest)
            )
            # check if opening_time is in the past (if so, it is either already booked or will not be booked)
            if opening_time < datetime.now().astimezone():
                continue
            classes.append(c)
    return classes
