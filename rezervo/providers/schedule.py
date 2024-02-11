from typing import Union

import pytz

from rezervo.consts import WEEKDAYS
from rezervo.errors import BookingError
from rezervo.schemas.config.user import Class
from rezervo.schemas.schedule import RezervoClass, RezervoSchedule
from rezervo.utils.logging_utils import err


def find_class_in_schedule_by_config(
    _class_config: Class, schedule: RezervoSchedule
) -> Union[RezervoClass, BookingError]:
    if not 0 <= _class_config.weekday < len(WEEKDAYS):
        err.log(f"Invalid weekday number ({_class_config.weekday=})")
        return BookingError.MALFORMED_SEARCH
    weekday_str = WEEKDAYS[_class_config.weekday]
    result = None
    for day in schedule.days:
        if day.day_name != weekday_str:
            continue
        for c in day.classes:
            if c.activity.id != _class_config.activity_id:
                continue
            localized_start_time = c.start_time.astimezone(
                pytz.timezone("Europe/Oslo")
            )  # TODO: clean this
            time_matches = (
                localized_start_time.hour == _class_config.start_time.hour
                and localized_start_time.minute == _class_config.start_time.minute
            )
            if not time_matches:
                result = BookingError.INCORRECT_START_TIME
                continue
            return c
    if result is None:
        result = BookingError.CLASS_MISSING
    return result
