from typing import Dict, Any, Optional

from sit_rezervo.auth.sit import AuthenticationError
from sit_rezervo.errors import BookingError
from sit_rezervo.notify.slack import notify_auth_failure_slack, notify_booking_failure_slack, notify_booking_slack, \
    schedule_class_reminder_slack
from sit_rezervo.schemas.config import config


def notify_auth_failure(notifications_config: config.Notifications, error: AuthenticationError = None,
                        check_run: bool = False) -> None:
    slack_config = notifications_config.slack
    if slack_config is not None:
        return notify_auth_failure_slack(slack_config.bot_token, slack_config.channel_id, slack_config.user_id, error,
                                         check_run=check_run)
    print("[WARNING] No notification targets, auth failure notification will not be sent!")


def notify_booking_failure(notifications_config: config.Notifications, _class_config: config.Class, error: BookingError = None,
                           check_run: bool = False) -> None:
    slack_config = notifications_config.slack
    if slack_config is not None:
        return notify_booking_failure_slack(slack_config.bot_token, slack_config.channel_id,
                                            slack_config.user_id, _class_config, error, check_run)
    print("[WARNING] No notification targets, booking failure notification will not be sent!")


def notify_booking(notifications_config: config.Notifications, booked_class: Dict[str, Any], ical_url: str) -> None:
    slack_config = notifications_config.slack
    if slack_config is not None:
        scheduled_reminder_id = None
        if notifications_config.reminder_hours_before is not None:
            scheduled_reminder_id = schedule_class_reminder(notifications_config, booked_class)
        if notifications_config.transfersh is not None:
            transfersh_url = notifications_config.transfersh.url
        else:
            transfersh_url = None
        return notify_booking_slack(slack_config.bot_token, slack_config.channel_id, slack_config.user_id,
                                    notifications_config.host, booked_class, ical_url, transfersh_url,
                                    scheduled_reminder_id)
    print("[WARNING] No notification targets, booking notification will not be sent!")


def schedule_class_reminder(notifications_config: config.Notifications, booked_class: Dict[str, Any]) -> Optional[str]:
    slack_config = notifications_config.slack
    if slack_config is not None:
        return schedule_class_reminder_slack(slack_config.bot_token, slack_config.user_id, notifications_config.host,
                                             booked_class, notifications_config.reminder_hours_before)
    print("[WARNING] No notification targets, class reminder will not be sent!")
