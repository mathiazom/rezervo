from typing import Any, Optional, Union

from rezervo import models
from rezervo.active_integrations import get_integration
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.slack import delete_scheduled_dm_slack, notify_cancellation_slack
from rezervo.schemas.config.config import ConfigValue, Slack
from rezervo.schemas.config.user import Class, IntegrationIdentifier, IntegrationUser
from rezervo.schemas.schedule import RezervoClass
from rezervo.utils.logging_utils import warn


def find_authed_class_by_id(
    integration_user: IntegrationUser, config: ConfigValue, class_id: str
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    return get_integration(integration_user.integration).find_authed_class_by_id(
        integration_user, config, class_id
    )


def find_class(
    integration: IntegrationIdentifier, _class_config: Class
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    return get_integration(integration).find_class(_class_config)


def book_class(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    return get_integration(integration_user.integration).book_class(
        integration_user, _class, config
    )


def cancel_booking(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    res = get_integration(integration_user.integration).cancel_booking(
        integration_user, _class, config
    )
    if res is None:
        if config.notifications is not None and config.notifications.slack is not None:
            update_slack_notifications_with_cancellation(
                integration_user.integration, _class, config.notifications.slack
            )
        else:
            warn.log(
                "Slack notifications config not specified, no Slack notifications will updated after cancellation!"
            )
    return res


def update_slack_notifications_with_cancellation(
    integration: IntegrationIdentifier, _class: RezervoClass, slack_config: Slack
):
    if slack_config.user_id is None:
        return None
    with SessionLocal() as db:
        receipts = (
            db.query(models.SlackClassNotificationReceipt)
            .filter_by(
                class_id=str(_class.id),
                slack_user_id=slack_config.user_id,
                integration=integration,
                channel_id=slack_config.channel_id,
            )
            .all()
        )
    for receipt in receipts:
        notify_cancellation_slack(
            slack_config.bot_token, slack_config.channel_id, receipt.message_id
        )
        reminder_id = receipt.scheduled_reminder_id
        if reminder_id is not None:
            delete_scheduled_dm_slack(
                slack_config.bot_token,
                slack_config.user_id,
                reminder_id,
            )
    with SessionLocal() as db:
        for receipt in receipts:
            db.delete(receipt)
        db.commit()


def rezervo_class_from_integration_class_data(
    class_data: Any,
) -> Optional[RezervoClass]:
    return get_integration(class_data.integration).rezervo_class_from_class_data(
        class_data
    )
