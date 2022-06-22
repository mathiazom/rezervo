from pathlib import Path

# Absolute normalized path to the root directory of the app
APP_ROOT = Path(__file__).parent.resolve()

CONFIG_PATH = "config.yaml"

WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

AUTH_URL = "https://www.sit.no/"
BOOKING_URL = "https://www.sit.no/trening/gruppe"

ADD_BOOKING_URL = "https://ibooking.sit.no/webapp/api//Schedule/addBooking"
CLASSES_SCHEDULE_URL = 'https://ibooking.sit.no/webapp/api/Schedule/getSchedule'
TOKEN_VALIDATION_URL = "https://ibooking.sit.no/webapp/api/User/validateToken"
ICAL_URL = "https://ibooking.sit.no/webapp/api/Schedule/calendar"

SLACK_ACTION_ADD_BOOKING_TO_CALENDAR = "add_booking_to_calendar"
SLACK_ACTION_CANCEL_BOOKING = "cancel_booking"
