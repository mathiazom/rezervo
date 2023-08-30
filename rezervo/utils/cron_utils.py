import datetime
import re
from re import Pattern
from typing import AnyStr
from uuid import UUID

from crontab import CronItem, CronTab

from rezervo import models
from rezervo.integrations.active import get_integration
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
            jobs.append(p)
        j = build_cron_job_for_class(
            i, c, integration_config.integration, conf.config.cron, user
        )
        jobs.append(j)
    return jobs


def build_cron_comment_prefix_for_user_integration(
    user_id: UUID, integration: IntegrationIdentifier
):
    return f"{get_settings().CRON_JOB_COMMENT_PREFIX}-{user_id}-{integration.value}"


def build_cron_job_for_class(
    index: int,
    _class: Class,
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
        f"{_class.display_name}{' --- [precheck]' if precheck else ''}",
        pre_comment=True,
    )
    j.setall(
        *generate_booking_schedule(
            _class,
            cron_config,
            get_integration(integration).booking_open_days_before_class,
            precheck,
        )
    )
    return j


def generate_booking_schedule(
    _class: Class, cron_config: Cron, booking_open_days_before: int, precheck: bool
):
    # Using current datetime simply as a starting point
    # We really only care about the "wall clock" part, which is replaced by input values
    activity_time = datetime.datetime.now().replace(
        hour=_class.time.hour,
        minute=_class.time.minute,
        second=0,
        microsecond=0,  # Cosmetic only
    )
    # Back up time to give booking script some prep time
    booking_time = activity_time - datetime.timedelta(
        minutes=cron_config.preparation_minutes
    )
    # Handle case where backing up time changes the weekday (weekday 0 is Monday in datetime and Sunday in cron...)
    booking_weekday_delta = activity_time.weekday() - booking_time.weekday()
    booking_cron_weekday = (
        _class.weekday + 1 - booking_open_days_before - booking_weekday_delta
    ) % 7
    if precheck:
        precheck_time = booking_time - datetime.timedelta(
            hours=cron_config.precheck_hours
        )
        precheck_cron_weekday = (
            booking_cron_weekday - (booking_time.weekday() - precheck_time.weekday())
        ) % 7
        return precheck_time.minute, precheck_time.hour, "*", "*", precheck_cron_weekday
    return booking_time.minute, booking_time.hour, "*", "*", booking_cron_weekday


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
