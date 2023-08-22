import time
from datetime import datetime, timedelta
from typing import Optional, Union
from uuid import UUID

import pydantic
import requests

from sit_rezervo import models
from sit_rezervo.auth.sit import (
    AuthenticationError,
    authenticate_token,
    authenticate_session,
    USER_AGENT,
    fetch_public_token,
)
from sit_rezervo.booking import book_class, cancel_booking
from sit_rezervo.consts import (
    ICAL_URL,
    MY_SESSIONS_URL,
    WEEKDAYS,
    PLANNED_SESSIONS_NEXT_WHOLE_WEEKS,
    BOOKING_OPEN_DAYS_BEFORE_CLASS,
)
from sit_rezervo.database.crud import upsert_user_sessions
from sit_rezervo.database.database import SessionLocal
from sit_rezervo.errors import BookingError
from sit_rezervo.models import SessionState
from sit_rezervo.notify.notify import notify_booking
from sit_rezervo.schemas.config import config
from sit_rezervo.schemas.config.admin import AdminConfig
from sit_rezervo.schemas.config.stored import StoredConfig
from sit_rezervo.schemas.config.user import UserConfig
from sit_rezervo.schemas.schedule import SitClass, SitInstructor, SitSchedule
from sit_rezervo.schemas.session import SitSession, UserSession, session_state_from_sit
from sit_rezervo.utils.sit_utils import fetch_sit_schedule
from sit_rezervo.utils.time_utils import total_days_for_next_whole_weeks


def try_book_class(
    token: str,
    _class: SitClass,
    max_attempts: int,
    notifications_config: Optional[config.Notifications] = None,
) -> Optional[BookingError]:
    if max_attempts < 1:
        print(f"[ERROR] Max booking attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    booked = False
    attempts = 0
    while not booked:
        booked = book_class(token, _class.id)
        attempts += 1
        if booked:
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2**attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not booked:
        print(
            f"[ERROR] Booking failed after {attempts} attempt"
            + ("s" if attempts != 1 else "")
        )
        return BookingError.ERROR
    print(
        f"[INFO] Successfully booked class"
        + (f" after {attempts} attempts!" if attempts != 1 else "!")
    )
    if notifications_config:
        ical_url = f"{ICAL_URL}/?id={_class.id}&token={token}"
        notify_booking(notifications_config, _class, ical_url)
    return None


def try_cancel_booking(
    token: str, _class: SitClass, max_attempts: int
) -> Optional[BookingError]:
    if _class.userStatus not in ["booked", "waitlist"]:
        print(f"[ERROR] Class is not booked, cancellation is not possible")
        return BookingError.CANCELLING_WITHOUT_BOOKING
    if max_attempts < 1:
        print(f"[ERROR] Max booking cancellation attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    cancelled = False
    attempts = 0
    while not cancelled:
        cancelled = cancel_booking(token, _class.id)
        attempts += 1
        if cancelled:
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2**attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not cancelled:
        print(
            f"[ERROR] Booking cancellation failed after {attempts} attempt"
            + ("s" if attempts != 1 else "")
        )
        return BookingError.ERROR
    print(
        f"[INFO] Successfully cancelled booking"
        + (f" after {attempts} attempts!" if attempts != 1 else "!")
    )
    return None


def try_authenticate(
    email: str, password: str, max_attempts: int
) -> Union[str, AuthenticationError]:
    if max_attempts < 1:
        return AuthenticationError.ERROR
    success = False
    attempts = 0
    result = None
    while not success:
        result = authenticate_token(email, password)
        success = not isinstance(result, AuthenticationError)
        attempts += 1
        if success:
            break
        if result == AuthenticationError.INVALID_CREDENTIALS:
            print(
                "[ERROR] Invalid credentials, aborting authentication to avoid lockout"
            )
            break
        if result == AuthenticationError.AUTH_TEMPORARILY_BLOCKED:
            print("[ERROR] Authentication temporarily blocked, aborting")
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2**attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not success:
        print(
            f"[ERROR] Authentication failed after {attempts} attempt"
            + ("s" if attempts != 1 else "")
        )
    return result if result is not None else AuthenticationError.ERROR


def get_user_planned_sessions_from_schedule(
    user_config: UserConfig, schedule: SitSchedule
) -> list[SitClass]:
    if not user_config.active:
        return []
    classes: list[SitClass] = []
    for d in schedule.days:
        for c in d.classes:
            for uc in user_config.classes:
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
                # check if start time is too close to now (if so, it is either already booked or will not be booked)
                if start_time < datetime.now() + timedelta(
                    days=BOOKING_OPEN_DAYS_BEFORE_CLASS
                ):
                    continue
                classes.append(c)
    return classes


def pull_sessions(user_id: UUID = None):
    planned_sit_schedule = fetch_sit_schedule(
        fetch_public_token(),
        days=total_days_for_next_whole_weeks(PLANNED_SESSIONS_NEXT_WHOLE_WEEKS),
    )
    with SessionLocal() as db:
        db_configs_query = db.query(models.Config)
        if user_id is not None:
            db_configs_query = db_configs_query.filter(models.Config.user_id == user_id)
        db_configs: list[models.Config] = db_configs_query.all()
        for db_user_config in db_configs:
            user_id = db_user_config.user_id
            stored_config = StoredConfig.from_orm(db_user_config)
            user_config = stored_config.config
            admin_config: AdminConfig = stored_config.admin_config
            auth_session = authenticate_session(
                admin_config.auth.email, admin_config.auth.password
            )
            if isinstance(auth_session, AuthenticationError):
                print(
                    f"[ERROR] Authentication failed for '{admin_config.auth.email}', abort user sessions pull!"
                )
                continue
            try:
                res = auth_session.get(
                    MY_SESSIONS_URL, headers={"User-Agent": USER_AGENT}
                )
            except requests.exceptions.RequestException as e:
                print(
                    f"[ERROR] Failed to retrieve sessions for '{admin_config.auth.email}'",
                    e,
                )
                continue
            sessions_json = res.json()
            sit_sessions = pydantic.parse_obj_as(list[SitSession], sessions_json)
            past_and_imminent_sessions = [
                UserSession(
                    class_id=s.class_field.id,
                    user_id=user_id,
                    status=session_state_from_sit(s.status),
                    class_data=s.class_field,
                )
                for s in sit_sessions
            ]
            planned_sessions = get_user_planned_sessions_from_schedule(
                user_config, planned_sit_schedule
            )
            user_sessions = past_and_imminent_sessions + [
                UserSession(
                    class_id=p.id,
                    user_id=user_id,
                    status=SessionState.PLANNED,
                    class_data=p,
                )
                for p in planned_sessions
                if p.id not in [s.class_id for s in past_and_imminent_sessions]
            ]
            upsert_user_sessions(db, user_id, user_sessions)
