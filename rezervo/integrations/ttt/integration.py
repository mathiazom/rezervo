from rezervo.integrations.integration import Integration
from rezervo.integrations.ttt.booking import (
    find_fsc_class,
    find_fsc_class_by_id,
    try_book_fsc_class,
    try_cancel_fsc_booking,
)
from rezervo.integrations.ttt.schema import rezervo_class_from_fsc_class
from rezervo.integrations.ttt.sessions import fetch_fsc_sessions

integration = Integration(
    find_authed_class_by_id=find_fsc_class_by_id,
    find_class=find_fsc_class,
    book_class=try_book_fsc_class,
    cancel_booking=try_cancel_fsc_booking,
    fetch_sessions=fetch_fsc_sessions,
    rezervo_class_from_class_data=rezervo_class_from_fsc_class,
)
