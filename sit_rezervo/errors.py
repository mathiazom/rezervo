from enum import Enum, auto


class BookingError(Enum):
    ERROR = auto()
    MALFORMED_SEARCH = auto()
    MALFORMED_SCHEDULE = auto()
    MISSING_SCHEDULE_DAY = auto()
    INCORRECT_START_TIME = auto()
    CLASS_MISSING = auto()
    MALFORMED_CLASS = auto()
    TOO_LONG_WAITING_TIME = auto()
    INVALID_CONFIG = auto()
