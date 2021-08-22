import os
import time
from datetime import datetime
import re

import requests
import requests.utils
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.support.wait import WebDriverWait

from pytz import timezone
from dotenv import load_dotenv


# Create dummy form element to execute post request from web driver
# (assumes that the driver has loaded some page to create the form element on)
def driver_post(driver, path, params):
    return driver.execute_script("""
      const form = document.createElement('form');
      form.method = 'post';
      form.action = arguments[0];

      let params = arguments[1]
      for (const key in params) {
        if (params.hasOwnProperty(key)) {
          const hiddenField = document.createElement('input');
          hiddenField.type = 'hidden';
          hiddenField.name = key;
          hiddenField.value = params[key];
          form.appendChild(hiddenField);
        }
      }

      document.body.appendChild(form);
      form.submit();
    """, path, params)


# Add driver cookies to session cookie jar (overwrite with driver values in case of conflict)
def transfer_cookies_from_web_driver_to_session(driver, session):
    session.cookies = requests.utils.cookiejar_from_dict(
        {c['name']: c['value'] for c in driver.get_cookies()},
        cookiejar=session.cookies
    )


def authenticate():
    firefox_options = Options()
    firefox_options.add_argument("-headless")
    with webdriver.Firefox(options=firefox_options) as driver:
        print(f"Authenticating as {SIT_USERNAME}...")
        driver_post(
            driver,
            AUTH_URL,
            {
                "name": SIT_USERNAME,
                "pass": SIT_PASSWORD,
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
        # Extract token from booking iframe url
        driver.get("https://www.sit.no/trening/gruppe")
        src = driver.find_element_by_id("ibooking-iframe").get_attribute("src")
        token = re.search(r'token=(.*?)&', src).group(1)
        # Validate token
        token_validation = requests.post("https://ibooking.sit.no/webapp/api/User/validateToken", {"token": token})
        if token_validation.status_code != requests.codes.OK:
            print("[ERROR] Authentication failed, token probably expired")
            return
        token_info = token_validation.json()
        if 'info' in token_info and token_info['info'] == "client-readonly":
            print("[ERROR] Authentication failed")
            return
        print(f"Authentication done.")
        return token


def book_class(token, class_id):
    print(f"Booking class {class_id} with token {token}")
    response = requests.post(
        "https://ibooking.sit.no/webapp/api//Schedule/addBooking",
        {
            "classId": class_id,
            "token": token
        }
    )
    if response.status_code != requests.codes.OK:
        print("[ERROR] Booking failed: " + response.text)
        return False
    print("Successfully booked class!")
    return True


# Search the scheduled classes and return the first class matching the given arguments
def find_class(token, activity_id, weekday):
    print(f"Searching for class matching criteria: activity={activity_id} and weekday={weekday}")
    schedule_response = requests.get(
        f"https://ibooking.sit.no/webapp/api/Schedule/getSchedule?token={token}&studios={STUDIO}&lang=no"
    )
    if schedule_response.status_code != requests.codes.OK:
        print("[ERROR] Schedule get request denied")
        return
    schedule = schedule_response.json()
    if 'days' not in schedule:
        print("[ERROR] Malformed schedule, contains no days")
        return
    days = schedule['days']
    target_day = None
    for day in days:
        if 'dayName' in day and day['dayName'] == weekday:
            target_day = day
            break
    if target_day is None:
        print(f"[ERROR] Could not find requested day '{weekday}'")
        return
    classes = target_day['classes']
    for c in classes:
        if 'activityId' in c and c['activityId'] == activity_id:
            if 'name' in c:
                search_feedback = f"Found class matching criteria: \"{c['name']}\""
                if 'instructors' in c and len(c['instructors']) > 0 and 'name' in c['instructors'][0]:
                    search_feedback += f" with {c['instructors'][0]['name']}"
                else:
                    search_feedback += " (missing instructor)"
                if 'from' in c:
                    search_feedback += f" at {c['from']}"
                print(search_feedback)
                return c
            print("[ERROR] Found class, but data was malformed: " + c)
            return
    print("[ERROR] Could not find class matching criteria")


AUTH_URL = "https://www.sit.no/"

load_dotenv("sit_auth.env")
SIT_USERNAME = os.environ["SIT_USERNAME"]
SIT_PASSWORD = os.environ["SIT_PASSWORD"]

load_dotenv("booking.env")
STUDIO = os.environ['STUDIO']
ACTIVITY_ID = int(os.environ['ACTIVITY_ID'])
ACTIVITY_WEEKDAY = os.environ['ACTIVITY_WEEKDAY']

BOOKING_TIMEZONE = "Europe/Oslo"

MAX_BOOKING_ATTEMPTS = 10


def main():
    auth_token = authenticate()
    if auth_token is None:
        print("Abort!")
        return
    _class = find_class(auth_token, ACTIVITY_ID, ACTIVITY_WEEKDAY)
    if _class is None:
        print("Abort!")
        return
    if _class['bookable']:
        print("Booking is already open, booking now!")
        book_class(auth_token, _class['id'])
        return
    # Retrieve booking opening, and make sure it's timezone aware
    tz = timezone(BOOKING_TIMEZONE)
    opening_time = tz.localize(datetime.fromisoformat(_class['bookingOpensAt']))
    timedelta = opening_time - datetime.now(tz)
    # TODO: Add a waiting limit (to avoid possibly waiting for multiple days...)
    wait_time = timedelta.total_seconds()
    wait_minutes = int(wait_time / 60)
    wait_seconds = int(wait_time % 60)
    print(f"Scheduling booking at {datetime.now(tz) + timedelta} "
          f"(about {wait_minutes} minute{'s' if wait_minutes > 1 else ''} and "
          f"{wait_seconds} second{'s' if wait_seconds > 1 else ''} from now)")
    time.sleep(wait_time)
    print(f"Awoke at {datetime.now(tz)}")
    booked = False
    attempts = 0
    while not booked and attempts < MAX_BOOKING_ATTEMPTS:
        booked = book_class(auth_token, _class['id'])
        attempts += 1
    if not booked:
        print(f"[ERROR] Failed to book class after {attempts} attempt" + "s" if MAX_BOOKING_ATTEMPTS > 1 else "")


if __name__ == '__main__':
    main()
