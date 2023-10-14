from rezervo.integrations.integration import Integration
from rezervo.providers.brpsystems.booking import (
    find_fsc_class_by_id,
    try_book_fsc_class,
    try_cancel_fsc_booking,
    try_find_fsc_class,
)
from rezervo.providers.brpsystems.schema import rezervo_class_from_fsc_class
from rezervo.providers.brpsystems.sessions import fetch_fsc_sessions

integration = Integration(
    find_authed_class_by_id=find_fsc_class_by_id,
    find_class=try_find_fsc_class,
    book_class=try_book_fsc_class,
    cancel_booking=try_cancel_fsc_booking,
    fetch_sessions=fetch_fsc_sessions,
    rezervo_class_from_class_data=rezervo_class_from_fsc_class,
)
