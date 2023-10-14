import time
from datetime import datetime
from typing import Union

import requests

from rezervo.consts import (
    WEEKDAYS,
)
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.notify import notify_booking
from rezervo.providers.ibooking.auth import fetch_public_token, try_authenticate
from rezervo.providers.ibooking.consts import (
    ADD_BOOKING_URL,
    CANCEL_BOOKING_URL,
    CLASS_URL,
    ICAL_URL,
)
from rezervo.providers.ibooking.schedule import fetch_ibooking_schedule
from rezervo.providers.ibooking.schema import (
    IBookingClass,
    rezervo_class_from_ibooking_class,
)
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import Class, IntegrationUser
from rezervo.schemas.schedule import RezervoClass
from rezervo.utils.logging_utils import err
from rezervo.utils.str_utils import format_name_list_to_natural


def book_ibooking_class(token, class_id) -> bool:
    print(f"Booking class {class_id}")
    response = requests.post(ADD_BOOKING_URL, {"classId": class_id, "token": token})
    if response.status_code != requests.codes.OK:
        err.log("Booking attempt failed: " + response.text)
        # TODO: distinguish between "retryable" and "non-retryable" errors
        #       (e.g. should not retry if already booked)
        return False
    return True


def cancel_ibooking_booking(token, class_id) -> bool:
    print(f"Cancelling booking of class {class_id}")
    res = requests.post(CANCEL_BOOKING_URL, {"classId": class_id, "token": token})
    if res.status_code != requests.codes.OK:
        err.log("Booking cancellation attempt failed: " + res.text)
        return False
    body = res.json()
    if body["success"] is False:
        err.log("Booking cancellation attempt failed: " + body.errorMessage)
        return False
    if (
        "class" not in body
        or "userStatus" not in body["class"]
        or body["class"]["userStatus"] != "available"
    ):
        err.log("Booking cancellation attempt failed, class is still booked!")
        return False
    return True


# Search the scheduled classes and return the first class matching the given arguments
def find_public_ibooking_class(
    _class_config: Class,
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    token = fetch_public_token()
    if isinstance(token, AuthenticationError):
        err.log("Failed to fetch public token")
        return token
    print(f"Searching for class matching config: {_class_config}")
    schedule = fetch_ibooking_schedule(token, 7, _class_config.studio)
    if schedule is None:
        err.log("Schedule get request denied")
        return BookingError.ERROR
    days = schedule.days
    target_day = None
    if not 0 <= _class_config.weekday < len(WEEKDAYS):
        err.log(f"Invalid weekday number ({_class_config.weekday=})")
        return BookingError.MALFORMED_SEARCH
    weekday_str = WEEKDAYS[_class_config.weekday]
    for day in days:
        if day.dayName == weekday_str:
            target_day = day
            break
    if target_day is None:
        err.log(f"Could not find requested day '{weekday_str}'. To early?")
        return BookingError.MISSING_SCHEDULE_DAY
    classes = target_day.classes
    result = None
    for c in classes:
        if c.activityId != _class_config.activity:
            continue
        start_time = datetime.strptime(c.from_field, "%Y-%m-%d %H:%M:%S")
        time_matches = (
            start_time.hour == _class_config.time.hour
            and start_time.minute == _class_config.time.minute
        )
        if not time_matches:
            print(f"Found class, but start time did not match: {c}")
            result = BookingError.INCORRECT_START_TIME
            continue
        search_feedback = f'Found class: "{c.name}"'
        if len(c.instructors) > 0:
            search_feedback += (
                f" with {format_name_list_to_natural([i.name for i in c.instructors])}"
            )
        else:
            search_feedback += " (missing instructor)"
        search_feedback += f" at {c.from_field}"
        print(search_feedback)
        return rezervo_class_from_ibooking_class(c)
    err.log("Could not find class matching criteria")
    if result is None:
        result = BookingError.CLASS_MISSING
    return result


def find_authed_ibooking_class_by_id(
    integration_user: IntegrationUser, config: ConfigValue, class_id: str
) -> Union[RezervoClass, None, BookingError, AuthenticationError]:
    token = try_authenticate(integration_user, config.auth.max_attempts)
    if isinstance(token, AuthenticationError):
        err.log("Failed to authenticate to iBooking")
        return token
    print(f"Searching for class by id: {class_id}")
    class_response = requests.get(f"{CLASS_URL}?token={token}&id={class_id}&lang=no")
    if class_response.status_code != requests.codes.OK:
        err.log("Class get request failed")
        return BookingError.ERROR
    ibooking_class = IBookingClass(**class_response.json()["class"])
    if ibooking_class is None:
        return BookingError.CLASS_MISSING
    return rezervo_class_from_ibooking_class(ibooking_class)


def cancel_booking(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    if _class.userStatus not in ["booked", "waitlist"]:
        err.log("Class is not booked, cancellation is not possible")
        return BookingError.CANCELLING_WITHOUT_BOOKING
    if config.booking.max_attempts < 1:
        err.log("Max booking cancellation attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    auth_result = try_authenticate(integration_user, config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        err.log("Authentication failed")
        return auth_result
    token = auth_result
    cancelled = False
    attempts = 0
    while not cancelled:
        cancelled = cancel_ibooking_booking(token, _class.id)
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


def book_class(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    max_attempts = config.booking.max_attempts
    if max_attempts < 1:
        err.log("Max booking attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    print("Authenticating...")
    auth_result = try_authenticate(integration_user, config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        err.log("Authentication failed")
        return auth_result
    token = auth_result
    booked = False
    attempts = 0
    while not booked:
        booked = book_ibooking_class(token, _class.id)
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
        ical_url = f"{ICAL_URL}/?id={_class.id}&token={token}"
        notify_booking(config.notifications, _class, ical_url)
    return None
