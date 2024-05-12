import asyncio
import time
from datetime import datetime
from uuid import UUID

import psutil
import typer
import uvicorn
from apprise import NotifyType

from rezervo.api import api
from rezervo.chains.active import ACTIVE_CHAINS
from rezervo.chains.common import authenticate, book_class, find_class
from rezervo.cli.async_cli import AsyncTyper
from rezervo.cli.cron import cron_cli
from rezervo.cli.sessions import sessions_cli
from rezervo.cli.users import users_cli
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.apprise import aprs
from rezervo.notify.notify import notify_auth_failure, notify_booking_failure
from rezervo.schemas.config.user import (
    ChainIdentifier,
)
from rezervo.sessions import pull_sessions
from rezervo.utils.apprise_utils import aprs_ctx
from rezervo.utils.config_utils import class_config_recurrent_id
from rezervo.utils.logging_utils import log
from rezervo.utils.time_utils import readable_seconds

cli = AsyncTyper()
cli.add_typer(users_cli, name="users", help="Manage rezervo users")
cli.add_typer(cron_cli, name="cron", help="Manage cron jobs for automatic booking")
cli.add_typer(sessions_cli, name="sessions", help="Manage user sessions")


@cli.command()
async def book(
    chain_identifier: ChainIdentifier,
    user_id: UUID,
    class_id: str,
    check_run: bool = typer.Option(
        False, "--check", help="Perform a dry-run to verify that booking is possible"
    ),
) -> None:
    """
    Book the class with config index matching the given class id
    """
    log.debug("Loading config...")
    with SessionLocal() as db:
        user_config = crud.get_user_config_by_id(db, user_id)
        chain_user = crud.get_chain_user(db, chain_identifier, user_id)
    if user_config is None:
        log.error("Failed to load config, aborted.")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title=f"Failed to load '{chain_identifier}' user config",
                body=f"Failed to load user config when attempting to book '{chain_identifier}' class",
                attach=[error_ctx],
            )
        return
    config = user_config.config
    if chain_user is None:
        log.error(f"No {chain_identifier} user for given user id, aborted booking.")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Missing user when booking",
                body="No user for given user id when attempting to book class",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_auth_failure(
                config.notifications,
                error=AuthenticationError.ERROR,
                check_run=check_run,
            )
        return
    _class_config = None
    for r in chain_user.recurring_bookings:
        if class_config_recurrent_id(r) == class_id:
            _class_config = r
            break
    if _class_config is None:
        log.error(f"Recurring booking with id '{class_id}' not found")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Recurring booking not found",
                body="Recurring booking not found for given id",
                attach=[error_ctx],
            )
        return
    if config.booking.max_attempts < 1:
        log.error("Max booking attempts must be a positive number")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Invalid app-level booking config",
                body="Max booking attempts must be a positive number",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_booking_failure(
                config.notifications,
                _class_config,
                BookingError.INVALID_CONFIG,
                check_run,
            )
        return
    log.debug("Authenticating chain user...")
    auth_data = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_data, AuthenticationError):
        log.error("Abort")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Authentication failure",
                body="Failed to authenticate when attempting to book class",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_auth_failure(config.notifications, auth_data, check_run)
        return
    log.debug("Searching for class...")
    class_search_result = await find_class(chain_identifier, _class_config)
    if isinstance(class_search_result, AuthenticationError):
        log.error("Abort")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Authentication failure",
                body="Failed to authenticate when attempting to book class",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_auth_failure(config.notifications, class_search_result, check_run)
        return
    if isinstance(class_search_result, BookingError):
        log.error("Abort")
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Class retrieval failure",
                body="Failed to retrieve class when attempting to book",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_booking_failure(
                config.notifications, _class_config, class_search_result, check_run
            )
        return
    if check_run:
        log.info(":heavy_check_mark: Check complete, all seems fine.")
        raise typer.Exit()
    _class = class_search_result
    if _class.is_bookable:
        log.info("Booking is already open, booking now")
    else:
        delta_to_opening = _class.booking_opens_at - datetime.now().astimezone()
        wait_time = delta_to_opening.total_seconds()
        if wait_time < 0:
            # booking is not open, and booking_opens_at is in the past, so we missed it
            log.error("Booking is closed. Aborting.")
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Booking is closed",
                    body="Booking is closed, booking_opens_at is in the past",
                    attach=[error_ctx],
                )
            if config.notifications is not None:
                notify_booking_failure(
                    config.notifications,
                    _class_config,
                    BookingError.ERROR,
                    check_run,
                )
            raise typer.Exit(1)
        wait_time_string = readable_seconds(wait_time)
        if wait_time > config.booking.max_waiting_minutes * 60:
            log.error(
                f"Booking waiting time was {wait_time_string}, "
                f"but max is {config.booking.max_waiting_minutes} minutes. Aborting."
            )
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Booking waiting time too long",
                    body=(
                        f"Booking waiting time was {wait_time_string}, "
                        f"but max is {config.booking.max_waiting_minutes} minutes.\n"
                    ),
                    attach=[error_ctx],
                )
            if config.notifications is not None:
                notify_booking_failure(
                    config.notifications,
                    _class_config,
                    BookingError.TOO_LONG_WAITING_TIME,
                )
            raise typer.Exit(1)
        log.info(
            f"Scheduling booking at {datetime.now().astimezone() + delta_to_opening} "
            f"(about {wait_time_string} from now)"
        )
        time.sleep(wait_time)
        log.info(f"Awoke at {datetime.now().astimezone()}")
    log.debug("Booking class ...")
    booking_result = await book_class(chain_user.chain, auth_data, _class, config)
    if isinstance(booking_result, AuthenticationError):
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Authentication failure",
                body="Failed to authenticate when attempting to book class",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_auth_failure(config.notifications, booking_result, check_run)
        raise typer.Exit(1)
    if isinstance(booking_result, BookingError):
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Booking failure",
                body="Failed to book class",
                attach=[error_ctx],
            )
        if config.notifications is not None:
            notify_booking_failure(
                config.notifications, _class_config, booking_result, check_run
            )
        raise typer.Exit(1)
    log.debug("Pulling sessions ...")
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
    Start a web server

    Actually a wrapper around uvicorn, and supports passing additional options to the underlying uvicorn.run() command.
    """
    ctx.args.insert(0, f"{api.__name__}:api")
    uvicorn.main.main(args=ctx.args)


@cli.command(name="purge_slack_receipts")
def purge_slack_receipts_cli():
    """
    Purge expired Slack notification receipts
    """
    with SessionLocal() as db:
        purge_count = crud.purge_slack_receipts(db)
        if purge_count > 0:
            log.info(
                f"Purged {purge_count} expired Slack notification receipt{'s' if purge_count > 1 else ''}"
            )
        else:
            log.debug("No expired Slack notification receipts")


@cli.command(name="extend_auth_sessions")
async def extend_auth_sessions_cli():
    """
    Extend the lifetime of all active authentication sessions
    """
    extend_jobs = []
    with SessionLocal() as db:
        for chain in ACTIVE_CHAINS:
            for chain_user in crud.get_chain_users(db, chain.identifier):
                extend_jobs.append(chain.extend_auth_session(chain_user))
    await asyncio.gather(*extend_jobs)


@cli.command(name="purge_playwright")
def purge_playwright_cli(
    minutes: int = typer.Option(
        10,
        help="Purge Playwright browser instances older than this many minutes",
    )
):
    """
    Purge Playwright browser instances
    """
    current_time = time.time()
    for proc in psutil.process_iter(["pid", "cmdline"]):
        cmd = " ".join(proc.info["cmdline"])
        if "playwright/driver/node" in cmd or "firefox" in cmd:
            process_age_seconds = current_time - proc.create_time()
            if process_age_seconds > (minutes * 60):
                log.info(
                    f"Killing playwright process {proc.pid} because it is older than {minutes} minutes ({cmd})"
                )
                proc.kill()


@cli.callback()
def callback():
    """
    Automatic booking of group classes
    """
