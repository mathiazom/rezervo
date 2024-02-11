WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

# The number of whole weeks to fetch in addition to the rest of the current week when looking at planned sessions
PLANNED_SESSIONS_NEXT_WHOLE_WEEKS = 4

AUTH_LOCKOUT_DURATION_MINUTES = 60

SLACK_ACTION_ADD_BOOKING_TO_CALENDAR = "add_booking_to_calendar"
SLACK_ACTION_CANCEL_BOOKING = "cancel_booking"

CRON_PULL_SESSIONS_JOB_COMMENT = "pull sessions"
CRON_PULL_SESSIONS_SCHEDULE = "2,17,32,47 4-23 * * *"

CRON_REFRESH_CRON_JOB_COMMENT = "refresh cron"
CRON_REFRESH_CRON_SCHEDULE = "0,30 4-23 * * *"

CRON_PURGE_SLACK_RECEIPTS_JOB_COMMENT = "purge slack receipts"
CRON_PURGE_SLACK_RECEIPTS_SCHEDULE = "0 0 * * *"
