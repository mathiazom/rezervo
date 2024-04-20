WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

# The number of whole weeks to fetch in addition to the rest of the current week when looking at planned sessions
PLANNED_SESSIONS_NEXT_WHOLE_WEEKS = 4

BOOKING_INITIAL_BURST_ATTEMPTS = 5

SLACK_ACTION_ADD_BOOKING_TO_CALENDAR = "add_booking_to_calendar"
SLACK_ACTION_CANCEL_BOOKING = "cancel_booking"

# should match rezervo-web consts
URL_QUERY_PARAM_CLASS_ID = "c"
URL_QUERY_PARAM_ISO_WEEK = "w"

AVATAR_FILENAME_STEM = "avatar"
AVATAR_FILENAME_EXTENSION = "webp"
AVATAR_FILENAME = f"{AVATAR_FILENAME_STEM}.{AVATAR_FILENAME_EXTENSION}"
MAX_AVATAR_FILE_SIZE_BYTES = 20_000_000
AVATAR_THUMBNAIL_SIZES = {
    "small": 75,
    "medium": 500,
}
