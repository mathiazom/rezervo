from datetime import datetime
from typing import Optional

import pytz
import requests

from rezervo.errors import BookingError
from rezervo.http_client import HttpClient
from rezervo.models import SessionState
from rezervo.providers.brpsystems.schema import (
    BookingData,
    BookingType,
    BrpAuthData,
    BrpSubdomain,
)
from rezervo.schemas.schedule import BookingResult
from rezervo.utils.logging_utils import log

SCHEDULE_SEARCH_ATTEMPT_DAYS = 7
MAX_SCHEDULE_SEARCH_ATTEMPTS = 6


def booking_url(
    subdomain: BrpSubdomain,
    auth_data: BrpAuthData,
    start_time_point: Optional[datetime] = None,
) -> str:
    return (
        f"https://{subdomain}.brpsystems.com"
        f"/brponline/api/ver3/customers/{auth_data.username}/bookings/groupactivities"
        + (
            f"?startTimePoint={start_time_point.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S')}.000Z"
            if start_time_point is not None
            else ""
        )
    )


async def book_brp_class(
    subdomain: BrpSubdomain, auth_data: BrpAuthData, class_id: int
) -> BookingResult | BookingError:
    async with HttpClient.singleton().post(
        booking_url(subdomain, auth_data, datetime.now()),
        json={"groupActivity": class_id, "allowWaitingList": True},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_data.access_token}",
        },
    ) as res:
        if res.status != 201:
            log.error("Booking attempt failed: " + (await res.text()))
            return BookingError.ERROR
        booking_data = BookingData(**await res.json())
        return BookingResult(
            status=(
                SessionState.WAITLIST
                if booking_data.type is BookingType.WAITING_LIST
                else SessionState.BOOKED
            ),
            position_in_wait_list=(
                booking_data.waitingListBooking.waitingListPosition
                if booking_data.waitingListBooking is not None
                else None
            ),
        )


async def cancel_brp_booking(
    subdomain: BrpSubdomain,
    auth_data: BrpAuthData,
    booking_reference: int,
    booking_type: BookingType,
) -> bool:
    log.debug(f"Cancelling booking of class {booking_reference}")
    async with HttpClient.singleton().delete(
        f"{booking_url(subdomain, auth_data)}/{booking_reference}?bookingType={booking_type.value}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_data.access_token}",
        },
    ) as res:
        if res.status != requests.codes.NO_CONTENT:
            log.error("Booking cancellation attempt failed: " + (await res.text()))
            return False
    return True
