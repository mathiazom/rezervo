from datetime import datetime

import humanize
import typer
from cron_descriptor import CasingTypeEnum  # type: ignore[import-untyped]
from crontab import CronItem, CronTab
from tabulate import tabulate

from rezervo.cli.async_cli import AsyncTyper
from rezervo.cron import refresh_recurring_booking_cron_jobs
from rezervo.settings import get_settings
from rezervo.utils.cron_utils import (
    generate_cron_cli_command,
)
from rezervo.utils.logging_utils import log

cron_cli = AsyncTyper()


def upsert_cli_cron_job(
    crontab: CronTab,
    command: str,
    schedule: str,
    comment: str,
):
    full_comment = f"{get_settings().CRON_JOB_COMMENT_PREFIX} [{comment}]"
    j = CronItem(
        command=generate_cron_cli_command(command),
        comment=full_comment,
        pre_comment=True,
    )
    j.setall(schedule)
    crontab.remove_all(comment=full_comment)
    crontab.append(j)
    log.debug(f":heavy_check_mark: Cronjob '{comment}' created")


@cron_cli.command(name="init")
def initialize_cron():
    with CronTab(user=True) as crontab:
        upsert_cli_cron_job(
            crontab,
            command="cron refresh",
            schedule="0,30 4-23 * * *",
            comment="refresh booking cron jobs",
        )
        upsert_cli_cron_job(
            crontab,
            command="extend_auth_sessions",
            schedule="50 * * * *",
            comment="extend auth sessions",
        )
        upsert_cli_cron_job(
            crontab,
            command="sessions pull",
            schedule="2,17,32,47 4-23 * * *",
            comment="pull sessions",
        )
        upsert_cli_cron_job(
            crontab,
            command="purge_slack_receipts",
            schedule="0 0 * * *",
            comment="purge slack receipts",
        )
        upsert_cli_cron_job(
            crontab,
            command="purge_playwright",
            schedule="*/5 * * * *",
            comment="purge playwright processes",
        )


@cron_cli.command(name="refresh")
async def refresh_cron():
    initialize_cron()
    await refresh_recurring_booking_cron_jobs()


@cron_cli.callback(invoke_without_command=True)
def list_cron_jobs(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Include more details about each cron job"
    ),
):
    if ctx.invoked_subcommand is not None:
        return
    with CronTab(user=True) as crontab:
        print_table_data: list[tuple[datetime, str, str]] = []
        for j in crontab:
            description = j.description(
                use_24hour_time_format=True, casing_type=CasingTypeEnum.LowerCase
            )
            if not j.is_valid():
                print_table_data.append((None, f"{j.comment} (invalid)", description))  # type: ignore
                continue
            if not j.is_enabled():
                print_table_data.append((None, f"{j.comment} (disabled)", description))  # type: ignore
                continue
            next_run: datetime = j.schedule(date_from=datetime.now()).get_next()
            if next_run is None:
                print_table_data.append((None, j.comment, description))
                continue
            print_table_data.append((next_run, j.comment, description))
        # Sort by next run time, with jobs missing 'next_run' sorted last
        print_table_data.sort(key=lambda x: (x[0] is None, x[0]))
        print_table = []
        for next_run, comment, description in print_table_data:
            row = [humanize.naturaltime(next_run) if next_run else None, comment]
            print_table.append(row + [next_run, description] if verbose else row)
        headers = ["until next run", "comment"]
        if verbose:
            headers.extend(["next run timestamp", "description"])
        print(
            tabulate(
                print_table,
                headers=headers,
                tablefmt="rounded_outline",
            )
        )
