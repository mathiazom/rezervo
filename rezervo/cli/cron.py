from datetime import datetime

import humanize
import typer
from cron_descriptor import CasingTypeEnum
from crontab import CronItem, CronTab
from rich import print as rprint
from tabulate import tabulate

from rezervo.cli.async_cli import AsyncTyper
from rezervo.consts import (
    CRON_PULL_SESSIONS_JOB_COMMENT,
    CRON_PULL_SESSIONS_SCHEDULE,
    CRON_PURGE_SLACK_RECEIPTS_JOB_COMMENT,
    CRON_PURGE_SLACK_RECEIPTS_SCHEDULE,
    CRON_REFRESH_CRON_JOB_COMMENT,
    CRON_REFRESH_CRON_SCHEDULE,
)
from rezervo.cron import refresh_cron
from rezervo.schemas.config.config import read_app_config
from rezervo.settings import get_settings
from rezervo.utils.cron_utils import (
    generate_pull_sessions_command,
    generate_purge_slack_receipts_command,
    generate_refresh_cron_command,
)

cron_cli = AsyncTyper()


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
        for j in crontab:  # type: ignore
            description = j.description(
                use_24hour_time_format=True, casing_type=CasingTypeEnum.LowerCase
            )
            if not j.is_valid():
                print_table_data.append((None, f"{j.comment} (invalid)", description))
                continue
            if not j.is_enabled():
                print_table_data.append((None, f"{j.comment} (disabled)", description))
                continue
            next_run: datetime = j.schedule(date_from=datetime.now()).get_next()  # type: ignore
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
