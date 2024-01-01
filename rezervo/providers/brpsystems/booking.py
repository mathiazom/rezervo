from datetime import datetime
from typing import Optional

import pytz
import requests

from rezervo.providers.brpsystems.schema import (
    BookingType,
    BrpAuthResult,
    BrpSubdomain,
)
from rezervo.utils.logging_utils import err

SCHEDULE_SEARCH_ATTEMPT_DAYS = 7
MAX_SCHEDULE_SEARCH_ATTEMPTS = 6


def booking_url(
    subdomain: BrpSubdomain,
    auth_result: BrpAuthResult,
    start_time_point: Optional[datetime] = None,
) -> str:
    return (
        f"https://{subdomain}.brpsystems.com"
        f"/brponline/api/ver3/customers/{auth_result.username}/bookings/groupactivities"
        + (
            f"?startTimePoint={start_time_point.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S')}.000Z"
            if start_time_point is not None
            else ""
        )
    )


def book_brp_class(
    subdomain: BrpSubdomain, auth_result: BrpAuthResult, class_id: int
) -> bool:
    response = requests.post(
        booking_url(subdomain, auth_result, datetime.now()),
        json={"groupActivity": class_id, "allowWaitingList": True},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_result.access_token}",
        },
    )
    if response.status_code != 201:
        err.log("Booking attempt failed: " + response.text)
        return False
    return True


def cancel_brp_booking(
    subdomain: BrpSubdomain,
    auth_result: BrpAuthResult,
    booking_reference: int,
    booking_type: BookingType,
) -> bool:
    print(f"Cancelling booking of class {booking_reference}")
    res = requests.delete(
        f"{booking_url(subdomain, auth_result)}/{booking_reference}?bookingType={booking_type.value}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_result.access_token}",
        },
    )
    if res.status_code != requests.codes.NO_CONTENT:
        err.log("Booking cancellation attempt failed: " + res.text)
        return False
    return True
