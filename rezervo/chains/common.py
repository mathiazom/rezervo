from typing import Union
from uuid import UUID

from rezervo import models
from rezervo.chains.active import get_chain
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.slack import delete_scheduled_dm_slack, notify_cancellation_slack
from rezervo.providers.schema import AuthData, LocationIdentifier
from rezervo.schemas.config.config import ConfigValue, Slack
from rezervo.schemas.config.user import (
    ChainIdentifier,
    ChainUser,
    Class,
)
from rezervo.schemas.schedule import BookingResult, RezervoClass, RezervoSchedule
from rezervo.utils.logging_utils import log


async def find_class_by_id(
    chain_user: ChainUser,
    class_id: str,
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    return await get_chain(chain_user.chain).find_class_by_id(class_id)


async def find_class(
    chain_identifier: ChainIdentifier, _class_config: Class
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    return await get_chain(chain_identifier).find_class(_class_config)


async def authenticate(
    chain_user: ChainUser,
    max_attempts: int,
) -> Union[AuthData, AuthenticationError]:
    return await get_chain(chain_user.chain).try_authenticate(chain_user, max_attempts)


async def book_class(
    chain_identifier: ChainIdentifier,
    auth_data: AuthData,
    _class: RezervoClass,
    config: ConfigValue,
    user_id: UUID,
) -> Union[BookingResult, BookingError, AuthenticationError]:
    return await get_chain(chain_identifier).try_book_class(
        chain_identifier, auth_data, _class, config, user_id
    )


async def cancel_booking(
    chain_identifier: ChainIdentifier,
    auth_data: AuthData,
    _class: RezervoClass,
    config: ConfigValue,
    user_id: UUID,
) -> Union[None, BookingError, AuthenticationError]:
    res = await get_chain(chain_identifier).try_cancel_booking(
        auth_data, _class, config, user_id
    )
    if res is None:
        if config.notifications is not None and config.notifications.slack is not None:
            update_slack_notifications_with_cancellation(
                chain_identifier, _class, config.notifications.slack
            )
        else:
            log.warning(
                "Slack notifications config not specified, no Slack notifications will updated after cancellation"
            )
    return res


def update_slack_notifications_with_cancellation(
    chain_identifier: ChainIdentifier, _class: RezervoClass, slack_config: Slack
):
    if slack_config.user_id is None:
        return None
    with SessionLocal() as db:
        receipts = (
            db.query(models.SlackClassNotificationReceipt)
            .filter_by(
                class_id=_class.id,
                slack_user_id=slack_config.user_id,
                chain=chain_identifier,
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


async def fetch_week_schedule(
    chain_identifier: ChainIdentifier,
    compact_iso_week: str,
    locations: list[LocationIdentifier],
) -> RezervoSchedule:
    return await get_chain(chain_identifier).fetch_week_schedule(
        compact_iso_week, locations
    )
