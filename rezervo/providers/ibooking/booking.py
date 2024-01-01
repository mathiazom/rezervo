import requests

from rezervo.providers.ibooking.schema import (
    IBookingDomain,
)
from rezervo.providers.ibooking.urls import (
    ADD_BOOKING_URL,
    CANCEL_BOOKING_URL,
)
from rezervo.utils.logging_utils import err


def book_ibooking_class(domain: IBookingDomain, token: str, class_id: int) -> bool:
    # TODO: handle different domains
    print(f"Booking class {class_id}")
    response = requests.post(ADD_BOOKING_URL, {"classId": class_id, "token": token})
    if response.status_code != requests.codes.OK:
        err.log("Booking attempt failed: " + response.text)
        # TODO: distinguish between "retryable" and "non-retryable" errors
        #       (e.g. should not retry if already booked)
        return False
    return True


def cancel_booking(domain: IBookingDomain, token, class_id: int) -> bool:
    # TODO: handle different domains
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
