WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

# The number of whole weeks to fetch in addition to the rest of the current week when looking at planned sessions
PLANNED_SESSIONS_NEXT_WHOLE_WEEKS = 4

BOOKING_INITIAL_BURST_ATTEMPTS = 5

SLACK_ACTION_ADD_BOOKING_TO_CALENDAR = "add_booking_to_calendar"
SLACK_ACTION_CANCEL_BOOKING = "cancel_booking"

CRON_PULL_SESSIONS_JOB_COMMENT = "pull sessions"
CRON_PULL_SESSIONS_SCHEDULE = "2,17,32,47 4-23 * * *"

CRON_REFRESH_CRON_JOB_COMMENT = "refresh cron"
CRON_REFRESH_CRON_SCHEDULE = "0,30 4-23 * * *"

CRON_PURGE_SLACK_RECEIPTS_JOB_COMMENT = "purge slack receipts"
CRON_PURGE_SLACK_RECEIPTS_SCHEDULE = "0 0 * * *"

AVATAR_FILENAME_STEM = "avatar"
AVATAR_FILENAME_EXTENSION = "webp"
AVATAR_FILENAME = f"{AVATAR_FILENAME_STEM}.{AVATAR_FILENAME_EXTENSION}"
MAX_AVATAR_FILE_SIZE_BYTES = 20_000_000
AVATAR_THUMBNAIL_SIZES = {
    "small": 75,
    "medium": 500,
}
