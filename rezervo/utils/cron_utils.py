import asyncio
import re
from datetime import datetime, timedelta
from re import Pattern
from uuid import UUID

from crontab import CronItem, CronTab

from rezervo import models
from rezervo.chains.common import find_class
from rezervo.errors import AuthenticationError, BookingError
from rezervo.schemas.config.app import Cron
from rezervo.schemas.config.config import Config, read_app_config
from rezervo.schemas.config.user import (
    ChainConfig,
    ChainIdentifier,
    Class,
)
from rezervo.settings import get_settings
from rezervo.utils.config_utils import class_config_recurrent_id
from rezervo.utils.logging_utils import err, warn


def upsert_jobs_by_comment(
    crontab: CronTab, comment: str | Pattern[str], jobs: list[CronItem]
):
    crontab.remove_all(comment=comment)
    for j in jobs:
        crontab.append(j)


async def find_class_with_config_task(chain: ChainIdentifier, class_config: Class):
    return class_config, (await find_class(chain, class_config))


async def build_cron_jobs_from_config(
    conf: Config,
    chain_config: ChainConfig,
    user: models.User,
    existing_jobs: list[CronItem],
) -> list[CronItem]:
    if not chain_config.active or chain_config.recurring_bookings is None:
        return []
    jobs = []
    reusable_jobs = existing_jobs.copy()
    for class_config, _class in await asyncio.gather(
        *[
            find_class_with_config_task(chain_config.chain, rb)
            for rb in chain_config.recurring_bookings
        ]
    ):
        if (
            _class is None
            or isinstance(_class, BookingError)
            or isinstance(_class, AuthenticationError)
        ):
            # find existing cron jobs matching the booking command (with and without precheck)
            job_commands = [
                generate_booking_command(
                    chain_config.chain,
                    class_config_recurrent_id(class_config),
                    conf.config.cron,
                    user.id,
                    check,
                )
                for check in [True, False]
            ]
            reusing = False
            for i in reversed(range(len(reusable_jobs))):
                if reusable_jobs[i].command in job_commands:
                    jobs.append(reusable_jobs.pop(i))
                    reusing = True
            if reusing:
                warn.log(
                    f"Keeping existing cron job for missing class to ensure failure notification\n"
                    f"  (user='{user.name}' chain='{chain_config.chain}' {class_config})"
                )
            else:
                err.log(
                    f"Cron job could not be created for recurring booking!\n"
                    f"  (user='{user.name}' chain='{chain_config.chain}' {class_config})"
                )
            continue
        if (
            conf.config.cron.precheck_hours is not None
            and conf.config.cron.precheck_hours > 0
        ):
            jobs.append(
                build_booking_cron_job(
                    user,
                    chain_config.chain,
                    class_config,
                    _class.booking_opens_at,
                    conf.config.cron,
                    precheck=True,
                )
            )
        jobs.append(
            build_booking_cron_job(
                user,
                chain_config.chain,
                class_config,
                _class.booking_opens_at,
                conf.config.cron,
            )
        )
    return jobs


def build_cron_comment_prefix_for_user_chain(
    user_id: UUID, chain_identifier: ChainIdentifier
):
    return f"{build_cron_comment_prefix_for_user(user_id)}-{chain_identifier}"


def build_cron_comment_prefix_for_user(user_id: UUID):
    return f"{get_settings().CRON_JOB_COMMENT_PREFIX}-{user_id}"


def build_booking_cron_job(
    user: models.User,
    chain_identifier: ChainIdentifier,
    class_config: Class,
    booking_opens_at: datetime,
    cron_config: Cron,
    precheck: bool = False,
) -> CronItem:
    j = CronItem(
        command=generate_booking_command(
            chain_identifier,
            class_config_recurrent_id(class_config),
            cron_config,
            user.id,
            precheck,
        ),
        comment=f"{build_cron_comment_prefix_for_user_chain(user.id, chain_identifier)} --- {user.name} --- "
        f"{class_config.display_name}{' --- [precheck]' if precheck else ''}",
        pre_comment=True,
    )
    j.setall(
        *generate_booking_schedule(
            booking_opens_at,
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


def generate_cron_cli_command(command: str) -> str:
    cron_config = read_app_config().cron
    return (
        f"{generate_cron_cli_command_prefix(cron_config)}"
        f"{command}"
        f"{generate_cron_cli_command_logging_suffix(cron_config)}"
    )


async def build_cron_jobs_from_config_task(
    crontab: CronTab, config: Config, chain_config: ChainConfig, user: models.User
):
    comment_pattern = re.compile(
        f"^{build_cron_comment_prefix_for_user_chain(user.id, chain_config.chain)}.*$"
    )
    existing_jobs = list(crontab.find_comment(comment_pattern))
    jobs = await build_cron_jobs_from_config(config, chain_config, user, existing_jobs)
    return chain_config.chain, user.name, comment_pattern, jobs


def delete_booking_crontab(user_id: UUID):
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(f"^{build_cron_comment_prefix_for_user(user_id)}.*$"),
            [],
        )
