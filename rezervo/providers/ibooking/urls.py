AUTH_URL = "https://api.sit.no/api/ibooking/user/login"
BOOKING_URL = "https://ibooking.sit.no/webapp/timeplan/"
MY_SESSIONS_URL = "https://api.sit.no/api/ibooking/user/bookings"
ADD_BOOKING_URL = "https://ibooking.sit.no/webapp/api//Schedule/addBooking"
CANCEL_BOOKING_URL = "https://ibooking.sit.no/webapp/api//Schedule/cancelBooking"
CLASSES_SCHEDULE_URL = "https://ibooking.sit.no/webapp/api/Schedule/getSchedule"
CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH = 4
CLASS_URL = "https://ibooking.sit.no/webapp/api/Schedule/getClass"
TOKEN_VALIDATION_URL = "https://ibooking.sit.no/webapp/api/User/validateToken"
ICAL_URL = "https://ibooking.sit.no/webapp/api/Schedule/calendar"

SIT_ROOT_URL = "https://www.sit.no"
SIT_LOGIN_URL = f"{SIT_ROOT_URL}/profile"
SIT_OIDC_USER_COOKIE_ORIGIN = SIT_ROOT_URL
SIT_AUTH_COOKIE_URL = "https://sitnettprodb2c.b2clogin.com"

# TODO: generalize (using https://espern.no as an example of another domain)
