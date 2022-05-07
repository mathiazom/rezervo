import sys
import time
from datetime import datetime
import re
from typing import Optional, Dict, Any

import requests
import requests.utils
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.support.wait import WebDriverWait

from pytz import timezone

from config import Config
from consts import APP_ROOT, AUTH_URL, WEEKDAYS, CONFIG_PATH, ADD_BOOKING_URL, CLASSES_SCHEDULE_URL, \
    TOKEN_VALIDATION_URL, BOOKING_URL
from driver_utils import driver_post
from time_utils import readable_seconds


def authenticate(email: str, password: str) -> Optional[str]:
    firefox_options = Options()
    firefox_options.add_argument("-headless")
    with webdriver.Firefox(options=firefox_options) as driver:
        print(f"Authenticating as {email}...")
        driver_post(
            driver,
            AUTH_URL,
            {
                "name": email,
                "pass": password,
                "form_id": "user_login"
            }
        )
        # Wait until logged in
        try:
            WebDriverWait(driver, timeout=20).until(
                lambda d: str(d.current_url).find(AUTH_URL) != -1
            )
        except TimeoutException:
            print("[ERROR] Authentication failed")
            return None
        # Extract token from booking iframe url
        driver.get(BOOKING_URL)
        src = driver.find_element(By.ID, "ibooking-iframe").get_attribute("src")
        token_match = re.search(r'token=(.*?)&', src)
        if token_match is None:
            print("[ERROR] Could not extract authentication token, aborted.")
            return None
        token = token_match.group(1)
        # Validate token
        token_validation = requests.post(TOKEN_VALIDATION_URL, {"token": token})
        if token_validation.status_code != requests.codes.OK:
            print("[ERROR] Validation of authentication token failed, token probably expired")
            return None
        token_info = token_validation.json()
        if 'info' in token_info and token_info['info'] == "client-readonly":
            print("[ERROR] Authentication failed")
            return None
        print(f"Authentication done.")
        return token


# Search the scheduled classes and return the first class matching the given arguments
def find_class(token: str, _class_config: Config) -> Optional[Dict[str, Any]]:
    print(f"Searching for class matching config: {_class_config}")
    schedule_response = requests.get(
        f"{CLASSES_SCHEDULE_URL}?token={token}&studios={_class_config.studio}&lang=no"
    )
    if schedule_response.status_code != requests.codes.OK:
        print("[ERROR] Schedule get request denied")
        return None
    schedule = schedule_response.json()
    if 'days' not in schedule:
        print("[ERROR] Malformed schedule, contains no days")
        return None
    days = schedule['days']
    target_day = None
    if not 0 <= _class_config.weekday < len(WEEKDAYS):
        print(f"[ERROR] Invalid weekday number ({_class_config.weekday=})")
        return None
    weekday_str = WEEKDAYS[_class_config.weekday]
    for day in days:
        if 'dayName' in day and day['dayName'] == weekday_str:
            target_day = day
            break
    if target_day is None:
        print(f"[ERROR] Could not find requested day '{weekday_str}'")
        return None
    classes = target_day['classes']
    for c in classes:
        if 'activityId' not in c or c['activityId'] != _class_config.activity:
            continue
        start_time = datetime.strptime(c['from'], '%Y-%m-%d %H:%M:%S')
        time_matches = start_time.hour == _class_config.time.hour and start_time.minute == _class_config.time.minute
        if not time_matches:
            print("[INFO] Found class, but start time did not match: " + c)
            continue
        if 'name' not in c:
            print("[WARNING] Found class, but data was malformed: " + c)
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
    return None


def book_class(token, class_id) -> bool:
    print(f"Booking class {class_id}")
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


def try_book_class(token: str, class_id: int, max_attempts: int) -> None:
    if max_attempts < 1:
        print(f"[WARNING] Max booking attempts should be a positive number")
        return
    booked = False
    attempts = 0
    while not booked:
        booked = book_class(token, class_id)
        attempts += 1
        if attempts >= max_attempts:
            break
        time.sleep(2 ** attempts)
    if not booked:
        print(f"[ERROR] Failed to book class after {attempts} attempt" + "s" if attempts > 1 else "")
        return
    print(f"Successfully booked class" + (f" after {attempts} attempts!" if attempts > 1 else "!"))
    return


def main() -> None:
    if len(sys.argv) <= 1:
        print("[ERROR] No class index provided")
        return
    try:
        _class_id = int(sys.argv[1])
    except ValueError:
        print(f"[ERROR] Invalid class index '{sys.argv[1]}'")
        return
    print("Loading config...")
    config = Config.from_config_file(APP_ROOT / CONFIG_PATH)
    if config is None:
        print("[ERROR] Failed to load config, aborted.")
        return
    if not 0 <= _class_id < len(config.classes):
        print(f"[ERROR] Class index out of bounds")
        return
    _class_config = config.classes[_class_id]
    auth_token = authenticate(config.auth.email, config.auth.password)
    if auth_token is None:
        print("Abort!")
        return
    _class = find_class(auth_token, _class_config)
    if _class is None:
        print("Abort!")
        return
    if _class['bookable']:
        print("Booking is already open, booking now!")
        try_book_class(auth_token, _class['id'], config.booking.max_attempts)
        return
    # Retrieve booking opening, and make sure it's timezone aware
    tz = timezone(config.booking.timezone)
    opening_time = tz.localize(datetime.fromisoformat(_class['bookingOpensAt']))
    timedelta = opening_time - datetime.now(tz)
    wait_time = timedelta.total_seconds()
    wait_time_string = readable_seconds(wait_time)
    if wait_time > config.booking.max_waiting_minutes * 60:
        print(f"[ERROR] Booking waiting time was {wait_time_string}, "
              f"but max is {config.booking.max_waiting_minutes} minutes. Aborting.")
        return
    print(f"Scheduling booking at {datetime.now(tz) + timedelta} "
          f"(about {wait_time_string} from now)")
    time.sleep(wait_time)
    print(f"Awoke at {datetime.now(tz)}")
    try_book_class(auth_token, _class['id'], config.booking.max_attempts)


if __name__ == '__main__':
    main()
