from typing import Union

from rezervo.consts import WEEKDAYS
from rezervo.errors import BookingError
from rezervo.schemas.config.user import Class
from rezervo.schemas.schedule import RezervoClass, RezervoSchedule
from rezervo.utils.logging_utils import err, warn


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
            time_matches = (
                c.start_time.hour == _class_config.start_time.hour
                and c.start_time.minute == _class_config.start_time.minute
            )
            if not time_matches:
                result = BookingError.INCORRECT_START_TIME
                continue
            return c
    warn.log(f"Could not find class matching criteria: {_class_config}")
    if result is None:
        result = BookingError.CLASS_MISSING
    return result
