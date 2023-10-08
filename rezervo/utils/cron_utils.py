import re
from datetime import datetime, timedelta
from re import Pattern
from typing import AnyStr
from uuid import UUID

from crontab import CronItem, CronTab

from rezervo import models
from rezervo.errors import AuthenticationError, BookingError
from rezervo.integrations.common import find_class
from rezervo.schemas.config.config import Config, Cron
from rezervo.schemas.config.user import Class, IntegrationConfig, IntegrationIdentifier
from rezervo.settings import get_settings


def upsert_jobs_by_comment(
    crontab: CronTab, comment: str | Pattern[AnyStr], jobs: list[CronItem]
):
    crontab.remove_all(comment=comment)
    for j in jobs:
        crontab.append(j)


def build_cron_jobs_from_config(
    conf: Config, integration_config: IntegrationConfig, user: models.User
) -> list[CronItem]:
    if not integration_config.active or integration_config.classes is None:
        return []
    jobs = []
    for i, c in enumerate(integration_config.classes):
        if (
            conf.config.cron.precheck_hours is not None
            and conf.config.cron.precheck_hours > 0
        ):
            p = build_cron_job_for_class(
                i,
                c,
                integration_config.integration,
                conf.config.cron,
                user,
                precheck=True,
            )
            if p is not None:
                jobs.append(p)
        j = build_cron_job_for_class(
            i, c, integration_config.integration, conf.config.cron, user
        )
        if j is not None:
            jobs.append(j)
    return jobs


def build_cron_comment_prefix_for_user_integration(
    user_id: UUID, integration: IntegrationIdentifier
):
    return f"{get_settings().CRON_JOB_COMMENT_PREFIX}-{user_id}-{integration.value}"


def build_cron_job_for_class(
    index: int,
    _class_config: Class,
    integration: IntegrationIdentifier,
    cron_config: Cron,
    user: models.User,
    precheck: bool = False,
):
    j = CronItem(
        command=generate_booking_command(
            integration, index, cron_config, user.id, precheck
        ),
        comment=f"{build_cron_comment_prefix_for_user_integration(user.id, integration)} --- {user.name} --- "
        f"{_class_config.display_name}{' --- [precheck]' if precheck else ''}",
        pre_comment=True,
    )
    _class = find_class(IntegrationIdentifier(integration), _class_config)
    if isinstance(_class, BookingError) or isinstance(
        _class_config, AuthenticationError
    ):
        print("Failed to fetch class info for booking schedule")
        return None
    j.setall(
        *generate_booking_schedule(
            datetime.fromisoformat(_class.bookingOpensAt),
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
    integration: IntegrationIdentifier,
    index: int,
    cron_config: Cron,
    user_id: UUID,
    precheck: bool,
) -> str:
    program_command = (
        f"cd {cron_config.rezervo_dir} || exit 1; "
        f'{cron_config.python_path}/rezervo book {integration.value} "{user_id}"'
    )
    output_redirection = f">> {cron_config.log_path} 2>&1"
    if precheck:
        return f"{program_command} {index} --check {output_redirection}"
    return f"{program_command} {index} {output_redirection}"


def generate_pull_sessions_command(cron_config: Cron) -> str:
    return (
        f"cd {cron_config.rezervo_dir} || exit 1; "
        f"{cron_config.python_path}/rezervo sessions pull >> {cron_config.log_path} 2>&1"
    )


def upsert_booking_crontab(
    config: Config, integration_config: IntegrationConfig, user: models.User
):
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(
                f"^{build_cron_comment_prefix_for_user_integration(user.id, integration_config.integration)}.*$"
            ),
            build_cron_jobs_from_config(config, integration_config, user),
        )


def delete_booking_crontab(user_id: UUID, integration: IntegrationIdentifier):
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(
                f"^{build_cron_comment_prefix_for_user_integration(user_id, integration)}.*$"
            ),
            [],
        )
