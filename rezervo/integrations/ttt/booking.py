import time
from datetime import datetime, timedelta
from typing import List, Union

import pytz
import requests

from rezervo.consts import WEEKDAYS
from rezervo.errors import AuthenticationError, BookingError
from rezervo.integrations.ttt.auth import authenticate
from rezervo.integrations.ttt.schedule import fetch_fsc_schedule
from rezervo.integrations.ttt.schema import (
    BookingData,
    BookingType,
    BrpAuthResult,
    FscClass,
    rezervo_class_from_fsc_class,
    tz_aware_iso_from_fsc_date_str,
)
from rezervo.notify.notify import notify_booking
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import Class, IntegrationUser
from rezervo.schemas.schedule import RezervoClass
from rezervo.utils.logging_utils import err
from rezervo.utils.str_utils import format_name_list_to_natural


def booking_url(auth_result: BrpAuthResult) -> str:
    return f"https://3t.brpsystems.com/brponline/api/ver3/customers/{auth_result['username']}/bookings/groupactivities"


MAX_SEARCH_ATTEMPTS = 6


def find_fsc_class_by_id(
    integration_user: IntegrationUser, config: ConfigValue, class_id: str
) -> Union[RezervoClass, None, BookingError, AuthenticationError]:
    print(f"Searching for class by id: {class_id}")
    attempts = 0
    fsc_class = None
    now = datetime.now()
    from_date = datetime(now.year, now.month, now.day)
    batch_size = 7
    while attempts < MAX_SEARCH_ATTEMPTS:
        print(f"Searching for class starting at {from_date}")
        fsc_schedule = fetch_fsc_schedule(days=batch_size, from_date=from_date)
        if fsc_schedule is None:
            err.log("Class get request failed")
            return BookingError.ERROR
        fsc_class = next(
            (c for c in fsc_schedule if c.id == int(class_id)),
            None,
        )
        if fsc_class is not None:
            break
        from_date += timedelta(days=batch_size)
        attempts += 1
    if fsc_class is None:
        return BookingError.CLASS_MISSING
    return rezervo_class_from_fsc_class(fsc_class)


def try_find_fsc_class(
    _class_config: Class,
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    print(f"Searching for class matching config: {_class_config}")
    attempts = 0
    fsc_class = None
    now_date = datetime.now()
    from_date = datetime(now_date.year, now_date.month, now_date.day)
    batch_size = 7
    while attempts < MAX_SEARCH_ATTEMPTS:
        schedule = fetch_fsc_schedule(days=batch_size, from_date=from_date)
        if schedule is None:
            err.log("Schedule get request denied")
            return BookingError.ERROR
        search_result = find_fsc_class(_class_config, schedule)
        if search_result is not None:
            if fsc_class is None:
                fsc_class = search_result
            else:
                # Check if class has closer booking date than any already found class
                now = datetime.now().astimezone()
                new_booking_delta = abs(
                    now - datetime.fromisoformat(search_result.bookingOpensAt)
                )
                existing_booking_delta = abs(
                    now - datetime.fromisoformat(fsc_class.bookingOpensAt)
                )
                if new_booking_delta < existing_booking_delta:
                    fsc_class = search_result
                else:
                    break
        from_date += timedelta(days=batch_size)
        attempts += 1
    if fsc_class is None:
        err.log("Could not find class matching criteria")
    return fsc_class


def find_fsc_class(
    _class_config: Class,
    schedule: List[FscClass],
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    if not 0 <= _class_config.weekday < len(WEEKDAYS):
        err.log(f"Invalid weekday number ({_class_config.weekday=})")
        return BookingError.MALFORMED_SEARCH
    result = None
    for c in schedule:
        if c.groupActivityProduct.id != _class_config.activity:
            continue
        localized_start_time = datetime.fromisoformat(
            tz_aware_iso_from_fsc_date_str(c.duration.start)
        ).astimezone(pytz.timezone("Europe/Oslo"))
        time_matches = (
            localized_start_time.hour == _class_config.time.hour
            and localized_start_time.minute == _class_config.time.minute
        )
        if not time_matches:
            print(f"Found class, but start time did not match: {c}")
            result = BookingError.INCORRECT_START_TIME
            continue
        if localized_start_time.weekday() != _class_config.weekday:
            print(f"Found class, but weekday did not match: {c}")
            result = BookingError.MISSING_SCHEDULE_DAY
            continue
        search_feedback = f'Found class: "{c.name}"'
        if len(c.instructors) > 0:
            search_feedback += (
                f" with {format_name_list_to_natural([i.name for i in c.instructors])}"
            )
        else:
            search_feedback += " (missing instructor)"
        search_feedback += f" at {c.duration.start}"
        print(search_feedback)
        return rezervo_class_from_fsc_class(c)
    return result


def book_fsc_class(auth_result: BrpAuthResult, class_id: int) -> bool:
    response = requests.post(
        booking_url(auth_result),
        json={"groupActivity": class_id, "allowWaitingList": True},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_result['access_token']}",
        },
    )
    if response.status_code != 201:
        err.log("Booking attempt failed: " + response.text)
        return False
    return True


def try_book_fsc_class(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    max_attempts = config.booking.max_attempts
    if max_attempts < 1:
        err.log("Max booking attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    print("Authenticating...")
    auth_result = authenticate(integration_user.username, integration_user.password)
    if isinstance(auth_result, AuthenticationError):
        err.log("Authentication failed")
        return auth_result
    booked = False
    attempts = 0
    while not booked:
        booked = book_fsc_class(auth_result, _class.id)
        attempts += 1
        if booked:
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2**attempts
        print(f"Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not booked:
        err.log(
            f"Booking failed after {attempts} attempt" + ("s" if attempts != 1 else "")
        )
        return BookingError.ERROR
    print(
        "Successfully booked class"
        + (f" after {attempts} attempts!" if attempts != 1 else "!")
    )
    if config.notifications:
        notify_booking(config.notifications, _class)
    return None


def cancel_fsc_booking(
    auth_result: BrpAuthResult, booking_reference: int, booking_type: BookingType
) -> bool:
    print(f"Cancelling booking of class {booking_reference}")
    res = requests.delete(
        f"{booking_url(auth_result)}/{booking_reference}?bookingType={booking_type}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_result['access_token']}",
        },
    )
    if res.status_code != requests.codes.NO_CONTENT:
        err.log("Booking cancellation attempt failed: " + res.text)
        return False
    return True


def try_cancel_fsc_booking(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    if config.booking.max_attempts < 1:
        err.log("Max booking cancellation attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    print("Authenticating...")
    auth_result = authenticate(integration_user.username, integration_user.password)
    if isinstance(auth_result, AuthenticationError):
        err.log("Authentication failed")
        return auth_result
    try:
        res = requests.get(
            booking_url(auth_result),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_result['access_token']}",
            },
        )
    except requests.exceptions.RequestException as e:
        err.log(
            f"Failed to retrieve sessions for '{integration_user.username}'",
            e,
        )
        return BookingError.ERROR
    bookings_response: List[BookingData] = res.json()
    booking_id = None
    booking_type = None
    for booking in bookings_response:
        if booking["groupActivity"]["id"] == _class.id:
            booking_type = booking["type"]
            booking_id = booking[booking_type]["id"]
            break
    if booking_id is None or booking_type is None:
        err.log(
            f"No sessions active matching the cancellation criteria for class '{_class.id}'",
        )
        return BookingError.CLASS_MISSING
    cancelled = False
    attempts = 0
    while not cancelled:
        cancelled = cancel_fsc_booking(auth_result, booking_id, booking_type)
        attempts += 1
        if cancelled:
            break
        if attempts >= config.booking.max_attempts:
            break
        sleep_seconds = 2**attempts
        print(f"Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not cancelled:
        err.log(
            f"Booking cancellation failed after {attempts} attempt"
            + ("s" if attempts != 1 else "")
        )
        return BookingError.ERROR
    print(
        "Successfully cancelled booking"
        + (f" after {attempts} attempts!" if attempts != 1 else "!")
    )
    return None