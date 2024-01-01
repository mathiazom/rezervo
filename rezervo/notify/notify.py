from typing import Optional

from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.push import (
    notify_auth_failure_web_push,
    notify_booking_failure_web_push,
    notify_booking_web_push,
)
from rezervo.notify.slack import (
    notify_auth_failure_slack,
    notify_booking_failure_slack,
    notify_booking_slack,
    schedule_class_reminder_slack,
)
from rezervo.schemas.config import config
from rezervo.schemas.config.user import ChainIdentifier, Class
from rezervo.schemas.schedule import RezervoClass
from rezervo.utils.logging_utils import warn


def notify_auth_failure(
    notifications_config: config.Notifications,
    error: Optional[AuthenticationError] = None,
    check_run: bool = False,
) -> None:
    notified = False
    push_subscriptions = notifications_config.push_notification_subscriptions
    if push_subscriptions is not None:
        for subscription in push_subscriptions:
            notify_auth_failure_web_push(subscription, error, check_run)
            notified = True
    slack_config = notifications_config.slack
    if slack_config is not None and slack_config.user_id is not None:
        notify_auth_failure_slack(
            slack_config.bot_token,
            slack_config.channel_id,
            slack_config.user_id,
            error,
            check_run=check_run,
        )
        notified = True
    if not notified:
        warn.log("No notification targets, auth failure notification will not be sent!")


def notify_booking_failure(
    notifications_config: config.Notifications,
    _class_config: Optional[Class] = None,
    error: Optional[BookingError] = None,
    check_run: bool = False,
) -> None:
    notified = False
    push_subscriptions = notifications_config.push_notification_subscriptions
    if push_subscriptions is not None:
        for subscription in push_subscriptions:
            notify_booking_failure_web_push(
                subscription, _class_config, error, check_run
            )
            notified = True
    slack_config = notifications_config.slack
    if slack_config is not None and slack_config.user_id is not None:
        notify_booking_failure_slack(
            slack_config.bot_token,
            slack_config.channel_id,
            slack_config.user_id,
            _class_config,
            error,
            check_run,
        )
        notified = True
    if not notified:
        warn.log(
            "No notification targets, booking failure notification will not be sent!"
        )


def notify_booking(
    notifications_config: config.Notifications,
    chain_identifier: ChainIdentifier,
    booked_class: RezervoClass,
    ical_url: Optional[str] = None,
) -> None:
    notified = False
    push_subscriptions = notifications_config.push_notification_subscriptions
    if push_subscriptions is not None:
        for subscription in push_subscriptions:
            notify_booking_web_push(subscription, booked_class)
            notified = True
    slack_config = notifications_config.slack
    if slack_config is not None and slack_config.user_id is not None:
        scheduled_reminder_id = None
        if notifications_config.reminder_hours_before is not None:
            scheduled_reminder_id = schedule_class_reminder(
                notifications_config, chain_identifier, booked_class
            )
        if notifications_config.transfersh is not None:
            transfersh_url = notifications_config.transfersh.url
        else:
            transfersh_url = None
        notify_booking_slack(
            slack_config.bot_token,
            slack_config.channel_id,
            slack_config.user_id,
            notifications_config.host,
            chain_identifier,
            booked_class,
            ical_url,
            transfersh_url,
            scheduled_reminder_id,
        )
        notified = True
    if not notified:
        warn.log("No notification targets, booking notification will not be sent!")


def schedule_class_reminder(
    notifications_config: config.Notifications,
    chain_identifier: ChainIdentifier,
    booked_class: RezervoClass,
) -> Optional[str]:
    slack_config = notifications_config.slack
    if slack_config is not None and slack_config.user_id is not None:
        if notifications_config.reminder_hours_before is None:
            return None
        return schedule_class_reminder_slack(
            slack_config.bot_token,
            slack_config.user_id,
            notifications_config.host,
            chain_identifier,
            booked_class,
            notifications_config.reminder_hours_before,
        )
    warn.log("No notification targets, class reminder will not be sent!")
    return None
