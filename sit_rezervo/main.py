import time
from datetime import datetime
from typing import Optional, Dict, Any, Union

import typer
from pytz import timezone

from .auth import authenticate, AuthenticationError
from .booking import book_class, find_class
from .config import Config, config_from_stream, Notifications
from .consts import ICAL_URL
from .cron_generator import generate_booking_cron_job
from .errors import BookingError
from .notify.notify import notify_booking_failure, notify_booking, notify_auth_failure
from .utils.time_utils import readable_seconds

app = typer.Typer()


def try_book_class(token: str, _class: Dict[str, Any], max_attempts: int,
                   notifications_config: Optional[Notifications] = None) -> Optional[BookingError]:
    if max_attempts < 1:
        print(f"[ERROR] Max booking attempts should be a positive number")
        return BookingError.INVALID_CONFIG
    booked = False
    attempts = 0
    while not booked:
        booked = book_class(token, _class['id'])
        attempts += 1
        if booked:
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2 ** attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not booked:
        print(f"[ERROR] Booking failed after {attempts} attempt" + ("s" if attempts != 1 else ""))
        return BookingError.ERROR
    print(f"[INFO] Successfully booked class" + (f" after {attempts} attempts!" if attempts != 1 else "!"))
    if notifications_config:
        ical_url = f"{ICAL_URL}/?id={_class['id']}&token={token}"
        notify_booking(notifications_config, _class, ical_url)
    return None


def try_authenticate(email: str, password: str, max_attempts: int) -> Union[str, AuthenticationError]:
    if max_attempts < 1:
        return AuthenticationError.ERROR
    success = False
    attempts = 0
    result = None
    while not success:
        result = authenticate(email, password)
        success = not isinstance(result, AuthenticationError)
        attempts += 1
        if success:
            break
        if result == AuthenticationError.INVALID_CREDENTIALS:
            print("[ERROR] Invalid credentials, aborting authentication to avoid lockout")
            break
        if result == AuthenticationError.AUTH_TEMPORARILY_BLOCKED:
            print("[ERROR] Authentication temporarily blocked, aborting")
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2 ** attempts
        print(f"[INFO] Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not success:
        print(f"[ERROR] Authentication failed after {attempts} attempt" + ("s" if attempts != 1 else ""))
    return result if result is not None else AuthenticationError.ERROR


@app.command()
def book(
        class_id: int,
        check_run: bool = typer.Option(False, "--check", help="Perform a dry-run to verify that booking is possible"),
        config_stream: typer.FileText = typer.Option(
            "config.yaml",
            "--config-file", "-c",
            encoding="utf-8",
            help="Configurations file"
        ),
) -> None:
    print("[INFO] Loading config...")
    config = config_from_stream(config_stream)
    if config is None:
        print("[ERROR] Failed to load config, aborted.")
        return
    if not 0 <= class_id < len(config.classes):
        print(f"[ERROR] Class index out of bounds")
        return
    _class_config = config.classes[class_id]
    if config.booking.max_attempts < 1:
        print(f"[ERROR] Max booking attempts should be a positive number")
        if config.notifications is not None:
            notify_booking_failure(config.notifications, _class_config, BookingError.INVALID_CONFIG, check_run)
        return
    print("[INFO] Authenticating...")
    auth_result = try_authenticate(config.auth.email, config.auth.password, config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        print("[ERROR] Abort!")
        if config.notifications is not None:
            notify_auth_failure(config.notifications, auth_result, check_run)
        return
    class_search_result = find_class(auth_result, _class_config)
    if isinstance(class_search_result, BookingError):
        print("[ERROR] Abort!")
        if config.notifications is not None:
            notify_booking_failure(config.notifications, _class_config, class_search_result, check_run)
        return
    if check_run:
        print("[INFO] Check complete, all seems fine.")
        raise typer.Exit()
    _class = class_search_result
    if _class['bookable']:
        print("[INFO] Booking is already open, booking now!")
    else:
        # Retrieve booking opening, and make sure it's timezone aware
        tz = timezone(config.booking.timezone)
        opening_time = tz.localize(datetime.fromisoformat(_class['bookingOpensAt']))
        timedelta = opening_time - datetime.now(tz)
        wait_time = timedelta.total_seconds()
        wait_time_string = readable_seconds(wait_time)
        if wait_time > config.booking.max_waiting_minutes * 60:
            print(f"[ERROR] Booking waiting time was {wait_time_string}, "
                  f"but max is {config.booking.max_waiting_minutes} minutes. Aborting.")
            if config.notifications is not None:
                notify_booking_failure(config.notifications, _class_config, BookingError.TOO_LONG_WAITING_TIME)
            raise typer.Exit(1)
        print(f"[INFO] Scheduling booking at {datetime.now(tz) + timedelta} "
              f"(about {wait_time_string} from now)")
        time.sleep(wait_time)
        print(f"[INFO] Awoke at {datetime.now(tz)}")
    booking_result = try_book_class(auth_result, _class, config.booking.max_attempts, config.notifications)
    if isinstance(booking_result, BookingError):
        if config.notifications is not None:
            notify_booking_failure(config.notifications, _class_config, booking_result, check_run)
        raise typer.Exit(1)


@app.command()
def cron(
        output_file: Optional[typer.FileTextWrite] = typer.Option(None, "--output-file", "-o", encoding="utf-8"),
        config_stream: typer.FileText = typer.Option(
            "config.yaml",
            "--config-file", "-c",
            encoding="utf-8",
            help="Configurations file"
        ),
):
    """
    Generate cron jobs for class booking
    """
    config = config_from_stream(config_stream)
    cron_spec = ""
    for i, c in enumerate(config.classes):
        cron_spec += generate_booking_cron_job(i, c, config.cron, config_stream.name)
    if output_file is not None:
        output_file.write(cron_spec + "\n")
        raise typer.Exit()
    print(cron_spec)


@app.callback()
def callback():
    """
    Automatic booking of Sit Trening group classes
    """