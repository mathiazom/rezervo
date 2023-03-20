import time
from datetime import datetime
from typing import Optional
from uuid import UUID

import typer
import uvicorn
from pytz import timezone
from rich import print as rprint

from sit_rezervo import api, models
from sit_rezervo.api import delete_booking_crontab, upsert_booking_crontab
from sit_rezervo.auth.sit import AuthenticationError
from sit_rezervo.booking import find_class
from sit_rezervo.database import crud
from sit_rezervo.database.database import SessionLocal
from sit_rezervo.errors import BookingError
from sit_rezervo.main import try_book_class, try_authenticate
from sit_rezervo.notify.notify import notify_booking_failure, notify_auth_failure
from sit_rezervo.schemas.config.config import config_from_stored
from sit_rezervo.schemas.config.stored import StoredConfig
from sit_rezervo.utils.time_utils import readable_seconds

cli = typer.Typer()


@cli.command()
def book(
        user_id: UUID,
        class_id: int,
        check_run: bool = typer.Option(False, "--check", help="Perform a dry-run to verify that booking is possible")
) -> None:
    """
    Book the class with config index matching the given class id
    """
    print("[INFO] Loading config...")
    with SessionLocal() as db:
        db_config = db.query(models.Config).filter_by(user_id=user_id).one_or_none()
        if db_config is None:
            print("[ERROR] Failed to load config from database, aborted.")
            return
        config = config_from_stored(StoredConfig.from_orm(db_config)).config
    if config is None:
        print("[ERROR] Failed to load config, aborted.")
        return
    if config.classes is None or not 0 <= class_id < len(config.classes):
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


@cli.command(
    name="api",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}  # Enabled to support uvicorn options
)
def serve_api(
        ctx: typer.Context
):
    """
    Start a web server to handle Slack message interactions

    Actually a wrapper around uvicorn, and supports passing additional options to the underlying uvicorn.run() command.
    """
    ctx.args.insert(0, f"{api.__name__}:api")
    uvicorn.main.main(args=ctx.args)

@cli.command(name="refreshcron")
def refresh_cron():
    with SessionLocal() as db:
        for c in db.query(models.Config).all():
            config = config_from_stored(StoredConfig.from_orm(c))
            db_user = db.get(models.User, config.user_id)
            upsert_booking_crontab(config, db_user)

@cli.command(name="createuser")
def create_user(
        name: str,
        jwt_sub: str,
        sit_email: str,
        sit_password: str,
        slack_id: Optional[str] = typer.Option(None)
):
    with SessionLocal() as db:
        db_user = crud.create_user(db, name, jwt_sub)
        crud.create_config(
            db,
            db_user.id,
            sit_email,
            sit_password,
            slack_id
        )
        rprint(f"User '{db_user.name}' created")


@cli.command(name="deleteuser")
def delete_user(
        user_id: UUID
):
    with SessionLocal() as db:
        config: models.Config = db.query(models.Config).filter_by(user_id=user_id).first()
        if config is not None:
            delete_booking_crontab(config.id)
        crud.delete_user(db, user_id)


@cli.callback()
def callback():
    """
    Automatic booking of Sit Trening group classes
    """
