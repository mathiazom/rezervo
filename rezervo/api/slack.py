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
from rezervo.chains.common import authenticate, cancel_booking, find_class_by_id
from rezervo.consts import (
    SLACK_ACTION_ADD_BOOKING_TO_CALENDAR,
    SLACK_ACTION_CANCEL_BOOKING,
)
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.notify.slack import (
    notify_cancellation_failure_slack,
    notify_working_slack,
    show_unauthorized_action_modal_slack,
    verify_slack_request,
)
from rezervo.schemas.config.config import Config, ConfigValue
from rezervo.schemas.slack import CancelBookingActionValue, Interaction
from rezervo.sessions import pull_sessions
from rezervo.utils.logging_utils import err, warn

router = APIRouter()


async def handle_cancel_booking_slack_action(
    user_id: UUID,
    config: ConfigValue,
    action_value: CancelBookingActionValue,
    message_ts: str,
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
        chain_user = crud.get_chain_user(db, action_value.chain_identifier, user_id)
    if chain_user is None:
        err.log("Chain user not found, abort!")
        if slack_config is not None:
            notify_cancellation_failure_slack(
                slack_config.bot_token,
                slack_config.channel_id,
                message_ts,
                AuthenticationError.ERROR,
            )
        return
    _class_res = await find_class_by_id(chain_user, action_value.class_id)
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
    print("Authenticating chain user...")
    auth_data = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_data, AuthenticationError):
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    cancellation_error = await cancel_booking(
        chain_user.chain, auth_data, _class_res, config
    )
    if cancellation_error is not None:
        if slack_config is not None:
            notify_cancellation_failure_slack(
                slack_config.bot_token,
                slack_config.channel_id,
                message_ts,
                cancellation_error,
            )
        return
    await pull_sessions(action_value.chain_identifier, user_id)


@router.post("/slackinteraction")
async def slack_action(
    request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    raw_body = await request.body()  # must read body before retrieving form data
    payload = (await request.form())["payload"]
    interaction: Interaction = pydantic.parse_raw_as(type_=Interaction, b=payload)  # type: ignore
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
        if action_value.user_id is None or action_value.user_id != interaction.user.id:
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
        background_tasks.add_task(
            handle_cancel_booking_slack_action,
            user_config.user_id,
            config,
            action_value,
            interaction.container.message_ts,
        )
        return Response(status_code=status.HTTP_200_OK)
    return Response(
        "Unsupported interaction action", status_code=status.HTTP_400_BAD_REQUEST
    )


def find_config_by_slack_id(configs: list[Config], user_id: str) -> Optional[Config]:
    if user_id is None:
        return None
    for config in configs:
        if (
            config.config.notifications is None
            or config.config.notifications.slack is None
        ):
            continue
        if config.config.notifications.slack.user_id == user_id:
            return config
    return None
