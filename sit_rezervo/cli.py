import time
from datetime import datetime
from typing import Optional
from uuid import UUID

import typer
import uvicorn
from crontab import CronTab, CronItem
from pytz import timezone
from rich import print as rprint

from sit_rezervo import api, models
from sit_rezervo.api import delete_booking_crontab, upsert_booking_crontab
from sit_rezervo.auth.sit import AuthenticationError
from sit_rezervo.booking import find_class
from sit_rezervo.consts import CRON_PULL_SESSIONS_JOB_COMMENT, CRON_PULL_SESSIONS_SCHEDULE
from sit_rezervo.database import crud
from sit_rezervo.database.database import SessionLocal
from sit_rezervo.errors import BookingError
from sit_rezervo.main import try_book_class, try_authenticate, pull_sessions
from sit_rezervo.notify.notify import notify_booking_failure, notify_auth_failure
from sit_rezervo.schemas.config.config import config_from_stored, read_app_config
from sit_rezervo.schemas.config.stored import StoredConfig
from sit_rezervo.settings import get_settings
from sit_rezervo.utils.cron_utils import generate_pull_sessions_command
from sit_rezervo.utils.time_utils import readable_seconds

cli = typer.Typer()
users_cli = typer.Typer()
cli.add_typer(users_cli, name="users")
cron_cli = typer.Typer()
cli.add_typer(cron_cli, name="cron")
sessions_cli = typer.Typer()
cli.add_typer(sessions_cli, name="sessions")


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
    pull_sessions()


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


@cron_cli.command(name="sessionsjob")
def create_cron_sessions_job():
    comment = f"{get_settings().CRON_JOB_COMMENT_PREFIX} [{CRON_PULL_SESSIONS_JOB_COMMENT}]"
    j = CronItem(
        command=generate_pull_sessions_command(read_app_config().cron),
        comment=comment,
        pre_comment=True
    )
    j.setall(CRON_PULL_SESSIONS_SCHEDULE)
    with CronTab(user=True) as crontab:
        crontab.remove_all(comment=comment)
        crontab.append(j)


@cron_cli.command(name="refresh")
def refresh_cron():
    with SessionLocal() as db:
        for c in db.query(models.Config).all():
            config = config_from_stored(StoredConfig.from_orm(c))
            db_user = db.get(models.User, config.user_id)
            upsert_booking_crontab(config, db_user)


@users_cli.command(name="create")
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


@users_cli.command(name="delete")
def delete_user(
        user_id: UUID
):
    with SessionLocal() as db:
        config: models.Config = db.query(models.Config).filter_by(user_id=user_id).first()
        if config is not None:
            delete_booking_crontab(config.id)
        crud.delete_user(db, user_id)



@sessions_cli.command(name="pull")
def pull_sessions_cli():
    pull_sessions()


@cli.callback()
def callback():
    """
    Automatic booking of Sit Trening group classes
    """
