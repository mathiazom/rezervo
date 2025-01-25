from enum import Enum
from typing import Optional
from uuid import UUID

from rezervo.database.crud import (
    get_friend_ids_in_class,
    get_user,
    get_user_push_notification_subscriptions,
)
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.push import (
    notify_auth_failure_web_push,
    notify_booking_failure_web_push,
    notify_booking_web_push,
    notify_friend_of_booking_web_push,
    notify_friend_of_cancellation_web_push,
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
from rezervo.utils.logging_utils import log


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
        log.warning(
            "No notification targets, auth failure notification will not be sent"
        )


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
        log.warning(
            "No notification targets, booking failure notification will not be sent"
        )


async def notify_booking(
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
        await notify_booking_slack(
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
        log.warning("No notification targets, booking notification will not be sent")


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
    log.warning("No notification targets, class reminder will not be sent")
    return None


class ClassFriendNotificationType(Enum):
    BOOKING = "booking"
    CANCELLATION = "cancellation"


async def notify_class_friends(
    user_id: UUID,
    booked_class: RezervoClass,
    notification_type: ClassFriendNotificationType,
) -> None:
    with SessionLocal() as db:
        user = get_user(db, user_id)
        if user is None:
            return
        friend_ids = get_friend_ids_in_class(db, user_id, booked_class.id)
    for friend_id in friend_ids:
        with SessionLocal() as db:
            push_subscriptions = get_user_push_notification_subscriptions(db, friend_id)
        if push_subscriptions is not None:
            for subscription in push_subscriptions:
                match notification_type:
                    case ClassFriendNotificationType.BOOKING:
                        notify_friend_of_booking_web_push(
                            subscription, booked_class, user.name
                        )
                    case ClassFriendNotificationType.CANCELLATION:
                        notify_friend_of_cancellation_web_push(
                            subscription, booked_class, user.name
                        )


async def notify_class_friends_of_booking(
    user_id: UUID,
    booked_class: RezervoClass,
) -> None:
    await notify_class_friends(
        user_id, booked_class, ClassFriendNotificationType.BOOKING
    )


async def notify_class_friends_of_cancellation(
    user_id: UUID,
    booked_class: RezervoClass,
) -> None:
    await notify_class_friends(
        user_id, booked_class, ClassFriendNotificationType.CANCELLATION
    )
