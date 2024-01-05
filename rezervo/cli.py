import time
from datetime import datetime
from typing import Optional
from uuid import UUID

import humanize
import typer
import uvicorn
from crontab import CronItem, CronTab
from rich import print as rprint

from rezervo import models
from rezervo.api import api
from rezervo.async_cli import AsyncTyper
from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.chains.common import book_class, find_class
from rezervo.consts import (
    CRON_PULL_SESSIONS_JOB_COMMENT,
    CRON_PULL_SESSIONS_SCHEDULE,
    CRON_PURGE_SLACK_RECEIPTS_JOB_COMMENT,
    CRON_PURGE_SLACK_RECEIPTS_SCHEDULE,
    CRON_REFRESH_CRON_JOB_COMMENT,
    CRON_REFRESH_CRON_SCHEDULE,
)
from rezervo.cron import refresh_cron
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.notify import notify_auth_failure, notify_booking_failure
from rezervo.schemas.config.config import (
    read_app_config,
)
from rezervo.schemas.config.user import (
    ChainIdentifier,
    ChainUserCredentials,
)
from rezervo.sessions import pull_sessions
from rezervo.settings import get_settings
from rezervo.utils.cron_utils import (
    delete_booking_crontab,
    generate_pull_sessions_command,
    generate_purge_slack_receipts_command,
    generate_refresh_cron_command,
)
from rezervo.utils.logging_utils import err, stat
from rezervo.utils.time_utils import readable_seconds

# TODO: move subcommands to separate files
cli = AsyncTyper()
users_cli = AsyncTyper()
cli.add_typer(users_cli, name="users", help="Manage rezervo users")
cron_cli = AsyncTyper()
cli.add_typer(cron_cli, name="cron", help="Manage cron jobs for automatic booking")
sessions_cli = AsyncTyper()
cli.add_typer(sessions_cli, name="sessions", help="Manage user sessions")


@cli.command()
async def book(
    chain_identifier: ChainIdentifier,
    user_id: UUID,
    class_id: int,
    check_run: bool = typer.Option(
        False, "--check", help="Perform a dry-run to verify that booking is possible"
    ),
) -> None:
    """
    Book the class with config index matching the given class id
    """
    with stat("Loading config..."):
        with SessionLocal() as db:
            user_config = crud.get_user_config_by_id(db, user_id)
            chain_user = crud.get_chain_user(db, chain_identifier, user_id)
        if user_config is None:
            err.log("Failed to load config, aborted.")
            return
        config = user_config.config
        if chain_user is None:
            err.log(f"No {chain_identifier} user for given user id, aborted booking.")
            if config.notifications is not None:
                notify_auth_failure(
                    config.notifications,
                    error=AuthenticationError.ERROR,
                    check_run=check_run,
                )
            return
    if chain_user.recurring_bookings is None or not 0 <= class_id < len(
        chain_user.recurring_bookings
    ):
        err.log("Class index out of bounds")
        return
    _class_config = chain_user.recurring_bookings[class_id]
    if config.booking.max_attempts < 1:
        err.log("Max booking attempts should be a positive number")
        if config.notifications is not None:
            notify_booking_failure(
                config.notifications,
                _class_config,
                BookingError.INVALID_CONFIG,
                check_run,
            )
        return
    with stat("Searching for class..."):
        class_search_result = await find_class(chain_identifier, _class_config)
        if isinstance(class_search_result, AuthenticationError):
            err.log("Abort!")
            if config.notifications is not None:
                notify_auth_failure(
                    config.notifications, class_search_result, check_run
                )
            return
        if isinstance(class_search_result, BookingError):
            err.log("Abort!")
            if config.notifications is not None:
                notify_booking_failure(
                    config.notifications, _class_config, class_search_result, check_run
                )
            return
    if check_run:
        print("Check complete, all seems fine.")
        raise typer.Exit()
    _class = class_search_result
    if _class.is_bookable:
        print("Booking is already open, booking now!")
    else:
        delta_to_opening = _class.booking_opens_at - datetime.now().astimezone()
        wait_time = delta_to_opening.total_seconds()
        wait_time_string = readable_seconds(wait_time)
        if wait_time > config.booking.max_waiting_minutes * 60:
            err.log(
                f"Booking waiting time was {wait_time_string}, "
                f"but max is {config.booking.max_waiting_minutes} minutes. Aborting."
            )
            if config.notifications is not None:
                notify_booking_failure(
                    config.notifications,
                    _class_config,
                    BookingError.TOO_LONG_WAITING_TIME,
                )
            raise typer.Exit(1)
        print(
            f"Scheduling booking at {datetime.now().astimezone() + delta_to_opening} "
            f"(about {wait_time_string} from now)"
        )
        time.sleep(wait_time)
        print(f"Awoke at {datetime.now().astimezone()}")
    with stat("Booking class..."):
        booking_result = book_class(chain_user, _class, config)
    if isinstance(booking_result, AuthenticationError):
        if config.notifications is not None:
            notify_auth_failure(config.notifications, booking_result, check_run)
        raise typer.Exit(1)
    if isinstance(booking_result, BookingError):
        if config.notifications is not None:
            notify_booking_failure(
                config.notifications, _class_config, booking_result, check_run
            )
        raise typer.Exit(1)
    with stat("Pulling sessions..."):
        await pull_sessions(chain_identifier, user_id)


@cli.command(
    name="api",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },  # Enabled to support uvicorn options
)
def serve_api(ctx: typer.Context):
    """
    Start a web server to handle Slack message interactions

    Actually a wrapper around uvicorn, and supports passing additional options to the underlying uvicorn.run() command.
    """
    ctx.args.insert(0, f"{api.__name__}:api")
    uvicorn.main.main(args=ctx.args)


@cron_cli.command(name="add_pull_sessions_job")
def create_cron_sessions_job():
    comment = (
        f"{get_settings().CRON_JOB_COMMENT_PREFIX} [{CRON_PULL_SESSIONS_JOB_COMMENT}]"
    )
    j = CronItem(
        command=generate_pull_sessions_command(read_app_config().cron),
        comment=comment,
        pre_comment=True,
    )
    j.setall(CRON_PULL_SESSIONS_SCHEDULE)
    with CronTab(user=True) as crontab:
        crontab.remove_all(comment=comment)
        crontab.append(j)
    rprint(":heavy_check_mark: Cronjob created for sessions pulling")


@cron_cli.command(name="add_refresh_cron_job")
def create_cron_refresh_job():
    comment = (
        f"{get_settings().CRON_JOB_COMMENT_PREFIX} [{CRON_REFRESH_CRON_JOB_COMMENT}]"
    )
    j = CronItem(
        command=generate_refresh_cron_command(read_app_config().cron),
        comment=comment,
        pre_comment=True,
    )
    j.setall(CRON_REFRESH_CRON_SCHEDULE)
    with CronTab(user=True) as crontab:
        crontab.remove_all(comment=comment)
        crontab.append(j)
    rprint(":heavy_check_mark: Cronjob created for refreshing crontab")


@cron_cli.command(name="add_slack_receipts_purging_job")
def create_cron_add_slack_receipts_purging_job():
    comment = f"{get_settings().CRON_JOB_COMMENT_PREFIX} [{CRON_PURGE_SLACK_RECEIPTS_JOB_COMMENT}]"
    j = CronItem(
        command=generate_purge_slack_receipts_command(read_app_config().cron),
        comment=comment,
        pre_comment=True,
    )
    j.setall(CRON_PURGE_SLACK_RECEIPTS_SCHEDULE)
    with CronTab(user=True) as crontab:
        crontab.remove_all(comment=comment)
        crontab.append(j)
    rprint(":heavy_check_mark: Cronjob created for purging slack notification receipts")


@cron_cli.command(name="refresh")
async def refresh_cron_cli():
    await refresh_cron()


@cron_cli.callback(invoke_without_command=True)
def list_cron_jobs(ctx: typer.Context):
    if ctx.invoked_subcommand is not None:
        return
    with CronTab(user=True) as crontab:
        print_lines: list[tuple[Optional[datetime], str]] = []
        for j in crontab:  # type: ignore
            if not j.is_valid():
                print_lines.append((None, f"{j.comment} (invalid)"))
                continue
            if not j.is_enabled():
                print_lines.append((None, f"{j.comment} (disabled)"))
                continue
            next_run: datetime = j.schedule(date_from=datetime.now()).get_next()  # type: ignore
            if next_run is None:
                print_lines.append((None, f"{j.comment} (next: failed to determine)"))
                continue
            print_lines.append(
                (
                    next_run,
                    f"{j.comment} (next: {next_run}, {humanize.naturaltime(next_run)})",
                )
            )
        # Sort by next run time, with jobs missing 'next_run' sorted last
        print_lines.sort(key=lambda x: (x[0] is None, x[0]))
        for _, line in print_lines:
            print(line)


@users_cli.command(name="create")
def create_user(
    name: str,
    jwt_sub: str,
    slack_id: Optional[str] = typer.Option(None),
):
    with SessionLocal() as db:
        db_user = crud.create_user(db, name, jwt_sub, slack_id)
        rprint(f"User '{db_user.name}' created")


@users_cli.command(name="integrate")
def upsert_chain_user(
    name: str,
    chain_identifier: ChainIdentifier,
    username: str,
    password: str,
):
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(name=name).first()  # type: ignore
        if user is None:
            rprint(f"User '{name}' not found")
            raise typer.Exit(1)
        crud.upsert_chain_user_creds(
            db,
            user.id,
            chain_identifier,
            ChainUserCredentials(username=username, password=password),
        )
        rprint(f"User '{user.name}' integrated with {get_chain(chain_identifier).name}")


@users_cli.command(name="delete")
def delete_user(user_id: UUID):
    with SessionLocal() as db:
        delete_booking_crontab(user_id)
        crud.delete_user(db, user_id)


@users_cli.callback(
    invoke_without_command=True,
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def list_users(
    ctx: typer.Context,
    print_uuid: bool = typer.Option(False, "--id", help="Print UUIDs of users"),
):
    if ctx.invoked_subcommand is None:
        with SessionLocal() as db:
            users = db.query(models.User).all()
            for user in users:
                print((f"{user.id} " if print_uuid else "") + str(user.name))


@sessions_cli.command(name="pull")
async def pull_sessions_cli(
    name: Optional[str] = typer.Option(None, help="Name of user to pull sessions for"),
    chain_identifier: Optional[ChainIdentifier] = typer.Option(
        None, "--chain", help="Identifier of chain to pull sessions from"
    ),
):
    if (
        chain_identifier is not None
        and chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS
    ):
        rprint(f"Chain '{chain_identifier}' not found")
        raise typer.Exit(1)
    user = None
    if name is not None:
        with SessionLocal() as db:
            user = db.query(models.User).filter_by(name=name).first()  # type: ignore
            if user is None:
                rprint(f"User '{name}' not found")
                raise typer.Exit(1)
    await pull_sessions(chain_identifier, user.id if user is not None else None)


@cli.command(name="purge_slack_receipts")
def purge_slack_receipts_cli():
    """
    Purge expired Slack notification receipts
    """
    with SessionLocal() as db:
        purge_count = crud.purge_slack_receipts(db)
        if purge_count > 0:
            rprint(
                f"Purged {purge_count} expired Slack notification receipt{'s' if purge_count > 1 else ''}"
            )
        else:
            rprint("No expired Slack notification receipts")


@cli.callback()
def callback():
    """
    Automatic booking of group classes
    """
