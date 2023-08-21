import secrets
from datetime import datetime

from icalendar import cal

from sit_rezervo.schemas.schedule import SitClass
from sit_rezervo.utils.str_utils import format_name_list_to_natural


def generate_calendar_token():
    return secrets.token_urlsafe()


def ical_event_from_sit_class(_class: SitClass, user_id: str) -> cal.Event:
    event = cal.Event()
    event.add('uid', f'sit-{_class.id}-{user_id}@rezervo.no')
    event.add('summary', _class.name)
    event.add('description', f"{_class.name}{f' med {format_name_list_to_natural([i.name for i in _class.instructors])}' if len(_class.instructors) > 0 else ''}")
    event.add('location', _class.studio.name)
    event.add('dtstart', datetime.fromisoformat(_class.from_field))
    event.add('dtend', datetime.fromisoformat(_class.to))
    event.add('dtstamp', datetime.now())
    return event
