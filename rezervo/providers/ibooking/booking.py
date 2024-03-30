from rezervo.http_client import HttpClient
from rezervo.providers.ibooking.schema import (
    IBookingDomain,
)
from rezervo.providers.ibooking.urls import (
    ADD_BOOKING_URL,
    CANCEL_BOOKING_URL,
)
from rezervo.utils.logging_utils import err


async def book_ibooking_class(
    domain: IBookingDomain, token: str, class_id: int
) -> bool:
    # TODO: handle different domains
    print(f"Booking class {class_id}")
    async with HttpClient.singleton().post(
        ADD_BOOKING_URL, data={"classId": class_id, "token": token}
    ) as response:
        if not response.ok:
            err.log("Booking attempt failed: " + (await response.text()))
            # TODO: distinguish between "retryable" and "non-retryable" errors
            #       (e.g. should not retry if already booked)
            return False
        return True


async def cancel_booking(domain: IBookingDomain, token, class_id: int) -> bool:
    # TODO: handle different domains
    print(f"Cancelling booking of class {class_id}")
    async with HttpClient.singleton().post(
        CANCEL_BOOKING_URL, data={"classId": class_id, "token": token}
    ) as res:
        if not res.ok:
            err.log("Booking cancellation attempt failed: " + (await res.text()))
            return False
        body = await res.json()
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
