from rezervo.integrations.integration import Integration
from rezervo.providers.ibooking.booking import (
    book_class,
    cancel_booking,
    find_authed_ibooking_class_by_id,
    find_public_ibooking_class,
)
from rezervo.providers.ibooking.schema import rezervo_class_from_ibooking_class
from rezervo.providers.ibooking.sessions import fetch_ibooking_sessions

integration = Integration(
    find_authed_class_by_id=find_authed_ibooking_class_by_id,
    find_class=find_public_ibooking_class,
    book_class=book_class,
    cancel_booking=cancel_booking,
    fetch_sessions=fetch_ibooking_sessions,
    rezervo_class_from_class_data=rezervo_class_from_ibooking_class,
)
