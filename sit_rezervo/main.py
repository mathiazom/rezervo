import time
from typing import Dict, Any, Optional, Union

import pydantic
import requests

from sit_rezervo import models
from sit_rezervo.auth.sit import AuthenticationError, authenticate_token, authenticate_session, USER_AGENT
from sit_rezervo.booking import book_class, cancel_booking
from sit_rezervo.consts import ICAL_URL, MY_SESSIONS_URL
from sit_rezervo.database.crud import upsert_user_sessions
from sit_rezervo.database.database import SessionLocal
from sit_rezervo.errors import BookingError
from sit_rezervo.notify.notify import notify_booking
from sit_rezervo.schemas.config import config
from sit_rezervo.schemas.config.admin import AdminConfig
from sit_rezervo.schemas.config.stored import StoredConfig
from sit_rezervo.schemas.session import SitSession, UserSession, session_state_from_sit


def try_book_class(token: str, _class: Dict[str, Any], max_attempts: int,
                   notifications_config: Optional[config.Notifications] = None) -> Optional[BookingError]:
    if max_attempts < 1:
        print(f"[ERROR] Max booking attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    booked = False
    attempts = 0
    while not booked:
        booked = book_class(token, _class['id'])
        attempts += 1
        if booked:
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2 ** attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not booked:
        print(f"[ERROR] Booking failed after {attempts} attempt" + ("s" if attempts != 1 else ""))
        return BookingError.ERROR
    print(f"[INFO] Successfully booked class" + (f" after {attempts} attempts!" if attempts != 1 else "!"))
    if notifications_config:
        ical_url = f"{ICAL_URL}/?id={_class['id']}&token={token}"
        notify_booking(notifications_config, _class, ical_url)
    return None


def try_cancel_booking(token: str, _class: Dict[str, Any], max_attempts: int) -> Optional[BookingError]:
    if _class["userStatus"] not in ["booked", "waitlist"]:
        print(f"[ERROR] Class is not booked, cancellation is not possible")
        return BookingError.CANCELLING_WITHOUT_BOOKING
    if max_attempts < 1:
        print(f"[ERROR] Max booking cancellation attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    cancelled = False
    attempts = 0
    while not cancelled:
        cancelled = cancel_booking(token, _class['id'])
        attempts += 1
        if cancelled:
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2 ** attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not cancelled:
        print(f"[ERROR] Booking cancellation failed after {attempts} attempt" + ("s" if attempts != 1 else ""))
        return BookingError.ERROR
    print(f"[INFO] Successfully cancelled booking" + (f" after {attempts} attempts!" if attempts != 1 else "!"))
    return None


def try_authenticate(email: str, password: str, max_attempts: int) -> Union[str, AuthenticationError]:
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
            print("[ERROR] Invalid credentials, aborting authentication to avoid lockout")
            break
        if result == AuthenticationError.AUTH_TEMPORARILY_BLOCKED:
            print("[ERROR] Authentication temporarily blocked, aborting")
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2 ** attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not success:
        print(f"[ERROR] Authentication failed after {attempts} attempt" + ("s" if attempts != 1 else ""))
    return result if result is not None else AuthenticationError.ERROR


def pull_sessions():
    with SessionLocal() as db:
        db_configs: list[models.Config] = db.query(models.Config).all()
        for db_user_config in db_configs:
            user_id = db_user_config.user_id
            admin_config: AdminConfig = StoredConfig.from_orm(db_user_config).admin_config
            auth_session = authenticate_session(admin_config.auth.email, admin_config.auth.password)
            if isinstance(auth_session, AuthenticationError):
                print(f"[ERROR] Authentication failed for '{admin_config.auth.email}', abort user sessions pull!")
                continue
            try:
                res = auth_session.get(MY_SESSIONS_URL, headers={'User-Agent': USER_AGENT})
            except requests.exceptions.RequestException as e:  # This is the correct syntax
                print(f"[ERROR] Failed to retrieve sessions for '{admin_config.auth.email}'", e)
                continue
            sessions_json = res.json()
            sit_sessions = pydantic.parse_obj_as(list[SitSession], sessions_json)
            user_sessions = [UserSession(
                class_id=s.timeid,
                user_id=user_id,
                status=session_state_from_sit(s.status)
            ) for s in sit_sessions]
            upsert_user_sessions(db, user_id, user_sessions)
