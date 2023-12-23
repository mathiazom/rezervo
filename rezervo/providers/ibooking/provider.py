from rezervo.errors import AuthenticationError
from rezervo.providers.ibooking.auth import authenticate_session
from rezervo.providers.ibooking.booking import (
    book_class,
    cancel_booking,
    find_authed_ibooking_class_by_id,
    find_public_ibooking_class,
)
from rezervo.providers.ibooking.schema import (
    IBookingDomain,
    rezervo_class_from_ibooking_class,
)
from rezervo.providers.ibooking.sessions import fetch_ibooking_sessions
from rezervo.providers.provider import Provider


# TODO: make iBooking domain configurable
def get_ibooking_provider(domain: IBookingDomain):
    return Provider(
        find_authed_class_by_id=find_authed_ibooking_class_by_id,
        find_class=find_public_ibooking_class,
        book_class=book_class,
        cancel_booking=cancel_booking,
        fetch_sessions=fetch_ibooking_sessions,
        rezervo_class_from_class_data=rezervo_class_from_ibooking_class,
        verify_authentication=lambda credentials: not isinstance(
            authenticate_session(credentials.username, credentials.password),
            AuthenticationError,
        ),
    )
