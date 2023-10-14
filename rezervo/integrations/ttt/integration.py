from rezervo.integrations.integration import Integration
from rezervo.providers.brpsystems.booking import (
    find_brp_class_by_id,
    try_book_brp_class,
    try_cancel_brp_booking,
    try_find_brp_class,
)
from rezervo.providers.brpsystems.schema import rezervo_class_from_brp_class
from rezervo.providers.brpsystems.sessions import fetch_brp_sessions

integration = Integration(
    find_authed_class_by_id=find_brp_class_by_id,
    find_class=try_find_brp_class,
    book_class=try_book_brp_class,
    cancel_booking=try_cancel_brp_booking,
    fetch_sessions=fetch_brp_sessions,
    rezervo_class_from_class_data=rezervo_class_from_brp_class,
)
