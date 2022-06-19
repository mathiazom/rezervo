from datetime import datetime
from typing import Union, Dict, Any

import requests

from config import Config
from consts import ADD_BOOKING_URL, CLASSES_SCHEDULE_URL, WEEKDAYS
from errors import BookingError


def book_class(token, class_id) -> bool:
    print(f"[INFO] Booking class {class_id}")
    response = requests.post(
        ADD_BOOKING_URL,
        {
            "classId": class_id,
            "token": token
        }
    )
    if response.status_code != requests.codes.OK:
        print("[ERROR] Booking attempt failed: " + response.text)
        return False
    return True


# Search the scheduled classes and return the first class matching the given arguments
def find_class(token: str, _class_config: Config) -> Union[Dict[str, Any], BookingError]:
    print(f"[INFO] Searching for class matching config: {_class_config}")
    schedule_response = requests.get(
        f"{CLASSES_SCHEDULE_URL}?token={token}&studios={_class_config.studio}&lang=no"
    )
    if schedule_response.status_code != requests.codes.OK:
        print("[ERROR] Schedule get request denied")
        return BookingError.ERROR
    schedule = schedule_response.json()
    if 'days' not in schedule:
        print("[ERROR] Malformed schedule, contains no days")
        return BookingError.MALFORMED_SCHEDULE
    days = schedule['days']
    target_day = None
    if not 0 <= _class_config.weekday < len(WEEKDAYS):
        print(f"[ERROR] Invalid weekday number ({_class_config.weekday=})")
        return BookingError.MALFORMED_SEARCH
    weekday_str = WEEKDAYS[_class_config.weekday]
    for day in days:
        if 'dayName' in day and day['dayName'] == weekday_str:
            target_day = day
            break
    if target_day is None:
        print(f"[ERROR] Could not find requested day '{weekday_str}'. To early?")
        return BookingError.MISSING_SCHEDULE_DAY
    classes = target_day['classes']
    result = None
    for c in classes:
        if 'activityId' not in c or c['activityId'] != _class_config.activity:
            continue
        start_time = datetime.strptime(c['from'], '%Y-%m-%d %H:%M:%S')
        time_matches = start_time.hour == _class_config.time.hour and start_time.minute == _class_config.time.minute
        if not time_matches:
            print("[INFO] Found class, but start time did not match: " + c)
            result = BookingError.INCORRECT_START_TIME
            continue
        if 'name' not in c:
            print("[WARNING] Found class, but the name is missing: " + c)
            result = BookingError.MALFORMED_CLASS
            continue
        search_feedback = f"Found class: \"{c['name']}\""
        if 'instructors' in c and len(c['instructors']) > 0 and 'name' in c['instructors'][0]:
            search_feedback += f" with {c['instructors'][0]['name']}"
        else:
            search_feedback += " (missing instructor)"
        if 'from' in c:
            search_feedback += f" at {c['from']}"
        print(search_feedback)
        return c
    print("[ERROR] Could not find class matching criteria")
    if result is None:
        result = BookingError.CLASS_MISSING
    return result
