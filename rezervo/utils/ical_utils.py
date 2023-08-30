import secrets
from datetime import datetime
from typing import Optional

from icalendar import cal  # type: ignore[import]

from rezervo.models import SessionState
from rezervo.schemas.schedule import UserSession
from rezervo.utils.str_utils import format_name_list_to_natural


def generate_calendar_token():
    return secrets.token_urlsafe()


def ical_event_from_session(session: UserSession) -> Optional[cal.Event]:
    _class = session.class_data
    if _class is None:
        return None
    event = cal.Event()
    event.add(
        "uid", f"{session.integration.value}-{_class.id}-{session.user_id}@rezervo.no"
    )
    event.add("summary", _class.name)
    event.add(
        "description",
        f"{_class.name}{f' med {format_name_list_to_natural([i.name for i in _class.instructors])}' if len(_class.instructors) > 0 else ''}",
    )
    event.add("location", _class.studio.name)
    event.add("dtstart", datetime.fromisoformat(_class.from_field))
    event.add("dtend", datetime.fromisoformat(_class.to))
    event.add("dtstamp", datetime.now())
    event.add(
        "status",
        "CONFIRMED"
        if session.status in [SessionState.BOOKED, SessionState.CONFIRMED]
        else "TENTATIVE",
    )
    event.add(
        "sequence",
        # Not strictly compliant, but the status will generally follow this order (except UNKNOWN)
        # so the sequence number will most likely increase monotonically
        {
            SessionState.UNKNOWN: 0,
            SessionState.PLANNED: 1,
            SessionState.WAITLIST: 2,
            SessionState.BOOKED: 3,
            SessionState.CONFIRMED: 4,
        }[session.status],
    )
    return event
