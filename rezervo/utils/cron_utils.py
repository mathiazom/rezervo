import asyncio
import re
from datetime import datetime, timedelta
from re import Pattern
from uuid import UUID

from crontab import CronItem, CronTab

from rezervo import models
from rezervo.chains.common import find_class
from rezervo.errors import AuthenticationError, BookingError
from rezervo.schemas.config.config import Config, Cron
from rezervo.schemas.config.user import (
    ChainConfig,
    ChainIdentifier,
)
from rezervo.schemas.schedule import RezervoClass
from rezervo.settings import get_settings
from rezervo.utils.config_utils import class_recurrent_id


def upsert_jobs_by_comment(
    crontab: CronTab, comment: str | Pattern[str], jobs: list[CronItem]
):
    crontab.remove_all(comment=comment)
    for j in jobs:
        crontab.append(j)


async def build_cron_jobs_from_config(
    conf: Config, chain_config: ChainConfig, user: models.User
) -> list[CronItem]:
    if not chain_config.active or chain_config.recurring_bookings is None:
        return []
    jobs = []
    for _class in await asyncio.gather(
        *[find_class(chain_config.chain, rb) for rb in chain_config.recurring_bookings]
    ):
        if (
            _class is None
            or isinstance(_class, BookingError)
            or isinstance(_class, AuthenticationError)
        ):
            continue
        if (
            conf.config.cron.precheck_hours is not None
            and conf.config.cron.precheck_hours > 0
        ):
            jobs.append(
                build_cron_job_for_class(
                    _class,
                    chain_config.chain,
                    conf.config.cron,
                    user,
                    precheck=True,
                )
            )
        jobs.append(
            build_cron_job_for_class(_class, chain_config.chain, conf.config.cron, user)
        )
    return jobs


def build_cron_comment_prefix_for_user_chain(
    user_id: UUID, chain_identifier: ChainIdentifier
):
    return f"{build_cron_comment_prefix_for_user(user_id)}-{chain_identifier}"


def build_cron_comment_prefix_for_user(user_id: UUID):
    return f"{get_settings().CRON_JOB_COMMENT_PREFIX}-{user_id}"


def build_cron_job_for_class(
    _class: RezervoClass,
    chain_identifier: ChainIdentifier,
    cron_config: Cron,
    user: models.User,
    precheck: bool = False,
) -> CronItem:
    j = CronItem(
        command=generate_booking_command(
            chain_identifier,
            class_recurrent_id(_class),
            cron_config,
            user.id,
            precheck,
        ),
        comment=f"{build_cron_comment_prefix_for_user_chain(user.id, chain_identifier)} --- {user.name} --- "
        f"{_class.activity.name}{' --- [precheck]' if precheck else ''}",
        pre_comment=True,
    )
    j.setall(
        *generate_booking_schedule(
            _class.booking_opens_at,
            cron_config,
            precheck,
        )
    )
    return j


def generate_booking_schedule(
    opening_time: datetime, cron_config: Cron, precheck: bool
):
    # making sure date and time strings are in system timezone
    system_opening_time = opening_time.astimezone()
    if precheck:
        precheck_time = system_opening_time - timedelta(
            hours=cron_config.precheck_hours
        )
        return (
            precheck_time.minute,
            precheck_time.hour,
            "*",
            "*",
            (precheck_time.weekday() + 1) % 7,
        )
    booking_time = system_opening_time - timedelta(
        minutes=cron_config.preparation_minutes
    )
    return (
        booking_time.minute,
        booking_time.hour,
        "*",
        "*",
        (booking_time.weekday() + 1) % 7,
    )


def generate_booking_command(
    chain_identifier: ChainIdentifier,
    recurrent_booking_id: str,
    cron_config: Cron,
    user_id: UUID,
    precheck: bool,
) -> str:
    program_command = (
        f"cd {cron_config.rezervo_dir} || exit 1; "
        f'{cron_config.python_path}/rezervo book {chain_identifier} "{user_id}"'
    )
    output_redirection = f">> {cron_config.log_path} 2>&1"
    if precheck:
        return f"{program_command} {recurrent_booking_id} --check {output_redirection}"
    return f"{program_command} {recurrent_booking_id} {output_redirection}"


def generate_cron_cli_command_prefix(cron_config: Cron) -> str:
    return f"cd {cron_config.rezervo_dir} || exit 1; {cron_config.python_path}/rezervo "


def generate_cron_cli_command_logging_suffix(cron_config: Cron) -> str:
    return f" >> {cron_config.log_path} 2>&1"


def generate_pull_sessions_command(cron_config: Cron) -> str:
    return (
        f"{generate_cron_cli_command_prefix(cron_config)}"
        f"sessions pull"
        f"{generate_cron_cli_command_logging_suffix(cron_config)}"
    )


def generate_refresh_cron_command(cron_config: Cron) -> str:
    return (
        f"{generate_cron_cli_command_prefix(cron_config)}"
        f"cron refresh"
        f"{generate_cron_cli_command_logging_suffix(cron_config)}"
    )


def generate_purge_slack_receipts_command(cron_config: Cron) -> str:
    return (
        f"{generate_cron_cli_command_prefix(cron_config)}"
        f"purge_slack_receipts"
        f"{generate_cron_cli_command_logging_suffix(cron_config)}"
    )


async def upsert_booking_crontab(
    config: Config, chain_config: ChainConfig, user: models.User
):
    jobs = await build_cron_jobs_from_config(config, chain_config, user)
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(
                f"^{build_cron_comment_prefix_for_user_chain(user.id, chain_config.chain)}.*$"
            ),
            jobs,
        )


def delete_booking_crontab(user_id: UUID):
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(f"^{build_cron_comment_prefix_for_user(user_id)}.*$"),
            [],
        )
