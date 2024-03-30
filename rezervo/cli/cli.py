import asyncio
import time
from datetime import datetime
from uuid import UUID

import typer
import uvicorn
from rich import print as rprint

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
from rezervo.notify.notify import notify_auth_failure, notify_booking_failure
from rezervo.schemas.config.user import (
    ChainIdentifier,
)
from rezervo.sessions import pull_sessions
from rezervo.utils.config_utils import class_config_recurrent_id
from rezervo.utils.logging_utils import err
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
    print("Loading config...")
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
    _class_config = None
    for r in chain_user.recurring_bookings:
        if class_config_recurrent_id(r) == class_id:
            _class_config = r
            break
    if _class_config is None:
        err.log(f"Recurring booking with id '{class_id}' not found")
        return
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
    print("Authenticating chain user...")
    auth_data = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_data, AuthenticationError):
        err.log("Abort!")
        if config.notifications is not None:
            notify_auth_failure(config.notifications, auth_data, check_run)
        return
    print("Searching for class...")
    class_search_result = await find_class(chain_identifier, _class_config)
    if isinstance(class_search_result, AuthenticationError):
        err.log("Abort!")
        if config.notifications is not None:
            notify_auth_failure(config.notifications, class_search_result, check_run)
        return
    if isinstance(class_search_result, BookingError):
        err.log("Abort!")
        if config.notifications is not None:
            notify_booking_failure(
                config.notifications, _class_config, class_search_result, check_run
            )
        return
    if check_run:
        rprint(":heavy_check_mark: Check complete, all seems fine.")
        raise typer.Exit()
    _class = class_search_result
    if _class.is_bookable:
        print("Booking is already open, booking now!")
    else:
        delta_to_opening = _class.booking_opens_at - datetime.now().astimezone()
        wait_time = delta_to_opening.total_seconds()
        if wait_time < 0:
            # booking is not open, and booking_opens_at is in the past, so we missed it
            err.log("Booking is closed. Aborting.")
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
    print("Booking class...")
    booking_result = await book_class(chain_user.chain, auth_data, _class, config)
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
    print("Pulling sessions...")
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
            rprint(
                f"Purged {purge_count} expired Slack notification receipt{'s' if purge_count > 1 else ''}"
            )
        else:
            rprint("No expired Slack notification receipts")


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


@cli.callback()
def callback():
    """
    Automatic booking of group classes
    """
