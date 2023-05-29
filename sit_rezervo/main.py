import time
from typing import Dict, Any, Optional, Union

from sit_rezervo.auth.sit import AuthenticationError, authenticate_token
from sit_rezervo.booking import book_class, cancel_booking
from sit_rezervo.consts import ICAL_URL
from sit_rezervo.errors import BookingError
from sit_rezervo.notify.notify import notify_booking
from sit_rezervo.schemas.config import config


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
    if _class["userStatus"] != "booked":
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
