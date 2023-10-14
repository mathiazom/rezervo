import json
from typing import Optional
from uuid import UUID

import pydantic
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette import status
from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import Response

from rezervo.api.common import get_db
from rezervo.consts import (
    SLACK_ACTION_ADD_BOOKING_TO_CALENDAR,
    SLACK_ACTION_CANCEL_BOOKING,
)
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.slack import (
    delete_scheduled_dm_slack,
    notify_cancellation_failure_slack,
    notify_cancellation_slack,
    notify_working_slack,
    show_unauthorized_action_modal_slack,
    verify_slack_request,
)
from rezervo.providers.common import cancel_booking, find_authed_class_by_id
from rezervo.schemas.config.config import Config, ConfigValue
from rezervo.schemas.slack import CancelBookingActionValue, Interaction
from rezervo.sessions import pull_sessions
from rezervo.utils.logging_utils import err, warn

router = APIRouter()


def handle_cancel_booking_slack_action(
    user_id: UUID,
    config: ConfigValue,
    action_value: CancelBookingActionValue,
    message_ts: str,
    response_url: str,
):
    if config.notifications is None:
        warn.log("Notifications config not specified, no notifications will be sent!")
        slack_config = None
    else:
        slack_config = config.notifications.slack
        if slack_config is None:
            warn.log(
                "Slack notifications config not specified, no Slack notifications will be sent!"
            )
        else:
            notify_working_slack(
                slack_config.bot_token, slack_config.channel_id, message_ts
            )
    with SessionLocal() as db:
        integration_user = crud.get_integration_user(
            db, action_value.integration, user_id
        )
    if integration_user is None:
        err.log("Integration user not found, abort!")
        if slack_config is not None:
            notify_cancellation_failure_slack(
                slack_config.bot_token,
                slack_config.channel_id,
                message_ts,
                AuthenticationError.ERROR,
            )
        return
    _class_res = find_authed_class_by_id(
        integration_user, config, action_value.class_id
    )
    match _class_res:
        case AuthenticationError():
            err.log("Authentication failed, abort!")
            if slack_config is not None:
                notify_cancellation_failure_slack(
                    slack_config.bot_token,
                    slack_config.channel_id,
                    message_ts,
                    _class_res,
                )
            return
        case BookingError():
            err.log("Class retrieval by id failed, abort!")
            if slack_config is not None:
                notify_cancellation_failure_slack(
                    slack_config.bot_token,
                    slack_config.channel_id,
                    message_ts,
                    _class_res,
                )
            return
    cancellation_error = cancel_booking(integration_user, _class_res, config)
    if cancellation_error is not None:
        if slack_config is not None:
            notify_cancellation_failure_slack(
                slack_config.bot_token,
                slack_config.channel_id,
                message_ts,
                cancellation_error,
            )
        return
    if slack_config is not None:
        if action_value.scheduled_reminder_id is not None:
            delete_scheduled_dm_slack(
                slack_config.bot_token,
                slack_config.user_id,
                action_value.scheduled_reminder_id,
            )
        notify_cancellation_slack(
            slack_config.bot_token, slack_config.channel_id, message_ts, response_url
        )
    pull_sessions(action_value.integration, user_id)


@router.post("/slackinteraction")
async def slack_action(
    request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    raw_body = await request.body()  # must read body before retrieving form data
    payload = (await request.form())["payload"]
    interaction: Interaction = pydantic.parse_raw_as(type_=Interaction, b=payload)
    if interaction.type != "block_actions":
        return Response(
            f"Unsupported interaction type '{interaction.type}'",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if len(interaction.actions) != 1:
        return Response(
            "Unsupported number of interaction actions",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    action = interaction.actions[0]
    if action.action_id == SLACK_ACTION_ADD_BOOKING_TO_CALENDAR:
        return Response(status_code=status.HTTP_200_OK)
    if action.action_id == SLACK_ACTION_CANCEL_BOOKING:
        raw_action_value = action.value
        if raw_action_value is None:
            err.log("No action value available, abort!")
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
        action_value = CancelBookingActionValue(**json.loads(raw_action_value))
        user_config = crud.get_user_config_by_slack_id(db, action_value.user_id)
        config = user_config.config if user_config is not None else None
        if user_config is None or config is None:
            err.log("Could not find config for Slack user, abort!")
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
        if (
            config.notifications is None
            or config.notifications.slack is None
            or not verify_slack_request(
                raw_body, request.headers, config.notifications.slack.signing_secret
            )
        ):
            return Response(
                "Authentication failed", status_code=status.HTTP_401_UNAUTHORIZED
            )
        # This check should be performed before retrieving config, but then we wouldn't be able to display a funny modal
        if action_value.user_id != interaction.user.id:
            warn.log("Detected cancellation attempt by an unauthorized user")
            if (
                config.notifications is not None
                and config.notifications.slack is not None
            ):
                background_tasks.add_task(
                    show_unauthorized_action_modal_slack,
                    config.notifications.slack.bot_token,
                    interaction.trigger_id,
                )
            return Response("Nice try 👏", status_code=status.HTTP_403_FORBIDDEN)
        message_ts = interaction.container.message_ts
        background_tasks.add_task(
            handle_cancel_booking_slack_action,
            user_config.user_id,
            config,
            action_value,
            message_ts,
            interaction.response_url,
        )
        return Response(status_code=status.HTTP_200_OK)
    return Response(
        "Unsupported interaction action", status_code=status.HTTP_400_BAD_REQUEST
    )


def find_config_by_slack_id(configs: list[Config], user_id: str) -> Optional[Config]:
    for config in configs:
        if (
            config.config.notifications is None
            or config.config.notifications.slack is None
        ):
            continue
        if config.config.notifications.slack.user_id == user_id:
            return config
    return None
