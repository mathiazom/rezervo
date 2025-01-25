import secrets
from datetime import datetime
from typing import Optional

import pytz
from icalendar import cal  # type: ignore[import]

from rezervo.consts import URL_QUERY_PARAM_CLASS_ID, URL_QUERY_PARAM_ISO_WEEK
from rezervo.models import SessionState
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import SessionRezervoClass, UserSession
from rezervo.utils.str_utils import format_name_list_to_natural
from rezervo.utils.time_utils import compact_iso_week_str


def generate_calendar_token():
    return secrets.token_urlsafe()


def ical_event_from_session(
    session: UserSession, timezone: str, host: str | None
) -> Optional[cal.Event]:
    _class = session.class_data
    if _class is None:
        return None
    event = cal.Event()
    event.add("uid", f"{session.chain}-{_class.id}-{session.user_id}@rezervo.no")
    event.add("summary", _class.activity.name)
    instructors_str = (
        f"med {format_name_list_to_natural([i.name for i in _class.instructors])}"
        if len(_class.instructors) > 0
        else ""
    )
    event.add(
        "description",
        f"{_class.activity.name} {instructors_str}",
    )
    if host is not None:
        event.add("url", activity_url(host, session.chain, _class))
    event.add(
        "location",
        (
            _class.location.studio + f" ({_class.location.room})"
            if _class.location.room
            else ""
        ),
    )
    # TODO: start and end times use a naughty timezone hack to make ical valid, check if any nicer solutions exists
    tz = pytz.timezone(timezone)
    event.add("dtstart", _class.start_time.astimezone(tz).replace(tzinfo=None))
    event.add("dtend", _class.end_time.astimezone(tz).replace(tzinfo=None))
    event.add("dtstamp", datetime.now())
    event.add(
        "status",
        (
            "CONFIRMED"
            if session.status in [SessionState.BOOKED, SessionState.CONFIRMED]
            else "TENTATIVE"
        ),
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
            SessionState.NOSHOW: 5,
        }[session.status],
    )
    return event


def activity_url(
    host: str, chain_identifier: ChainIdentifier, _class: SessionRezervoClass
):
    return (
        f"{host}/{chain_identifier}"
        f"?{URL_QUERY_PARAM_ISO_WEEK}={compact_iso_week_str(_class.start_time)}"
        f"&{URL_QUERY_PARAM_CLASS_ID}={_class.id}"
    )
