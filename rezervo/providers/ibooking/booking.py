from rezervo.errors import BookingError
from rezervo.http_client import HttpClient
from rezervo.models import SessionState
from rezervo.providers.ibooking.schema import (
    IBookingBookingResponse,
    IBookingDomain,
)
from rezervo.providers.ibooking.urls import (
    ADD_BOOKING_URL,
    CANCEL_BOOKING_URL,
)
from rezervo.schemas.schedule import BookingResult
from rezervo.utils.logging_utils import log


async def book_ibooking_class(
    domain: IBookingDomain, token: str, class_id: int
) -> BookingResult | BookingError:
    # TODO: handle different domains
    log.debug(f"Booking class {class_id}")
    async with HttpClient.singleton().post(
        ADD_BOOKING_URL, data={"classId": class_id, "token": token}
    ) as response:
        if not response.ok:
            log.error("Booking attempt failed: " + (await response.text()))
            # TODO: distinguish between "retryable" and "non-retryable" errors
            #       (e.g. should not retry if already booked)
            return BookingError.ERROR
        booking_response = IBookingBookingResponse(**await response.json())
        if not booking_response.success:
            return BookingError.ERROR

        return BookingResult(
            status=(
                SessionState.WAITLIST
                if booking_response.waitlist
                else SessionState.BOOKED
            ),
            position_in_wait_list=(
                booking_response.waitlist_position
                if booking_response.waitlist_position > 0
                else None
            ),
        )


async def cancel_booking(domain: IBookingDomain, token, class_id: int) -> bool:
    # TODO: handle different domains
    log.debug(f"Cancelling booking of class {class_id}")
    async with HttpClient.singleton().post(
        CANCEL_BOOKING_URL, data={"classId": class_id, "token": token}
    ) as res:
        if not res.ok:
            log.error("Booking cancellation attempt failed: " + (await res.text()))
            return False
        body = await res.json()
    if body["success"] is False:
        log.error("Booking cancellation attempt failed: " + body.errorMessage)
        return False
    if (
        "class" not in body
        or "userStatus" not in body["class"]
        or body["class"]["userStatus"] != "available"
    ):
        log.error("Booking cancellation attempt failed, class is still booked")
        return False
    return True
