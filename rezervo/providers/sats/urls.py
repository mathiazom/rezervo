BASE_PATH = "https://www.sats.no"

LOGIN_PATH = "/logg-inn"
AUTH_PATH = "/api/log-in"
BOOK_PATH = "/api/book"
UNBOOK_PATH = "/api/unbook"
BOOKINGS_PATH = "/min-side/kommende-trening"


AUTH_URL = BASE_PATH + AUTH_PATH
BOOKING_URL = BASE_PATH + BOOK_PATH
UNBOOK_URL = BASE_PATH + UNBOOK_PATH
BOOKINGS_URL = BASE_PATH + BOOKINGS_PATH


def schedule_url(club_ids: list[str]):
    return f"{BASE_PATH}/booke?clubIds={','.join(club_ids)}"
