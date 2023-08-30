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
    CANCELLING_WITHOUT_BOOKING = auto()


class AuthenticationError(Enum):
    ERROR = auto()
    TOKEN_EXTRACTION_FAILED = auto()
    TOKEN_VALIDATION_FAILED = auto()
    TOKEN_INVALID = auto()
    AUTH_TEMPORARILY_BLOCKED = auto()
    INVALID_CREDENTIALS = auto()
