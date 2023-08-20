import secrets
from datetime import datetime

from icalendar import cal

from sit_rezervo.schemas.schedule import SitClass


def generate_calendar_token():
    return secrets.token_urlsafe()


def ical_event_from_sit_class(_class: SitClass) -> cal.Event:
    event = cal.Event()
    event.add('summary', _class.name)
    event.add('dtstart', datetime.fromisoformat(_class.from_field))
    event.add('dtend', datetime.fromisoformat(_class.to))
    event.add('dtstamp', datetime.now())
    return event
