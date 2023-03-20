import json
from typing import List, Optional

import pydantic
from fastapi import FastAPI, status, Response, Request, BackgroundTasks, Depends
from starlette.datastructures import Headers
from pydantic import BaseModel
from slack_sdk.signature import SignatureVerifier

from .auth import AuthenticationError
from .booking import find_class_by_id
from .config import Config
from .consts import SLACK_ACTION_ADD_BOOKING_TO_CALENDAR, SLACK_ACTION_CANCEL_BOOKING
from .errors import BookingError
from .main import try_cancel_booking, try_authenticate
from .notify.slack import notify_cancellation_slack, notify_working_slack, \
    notify_cancellation_failure_slack, show_unauthorized_action_modal_slack

api = FastAPI()


def get_configs() -> Optional[list[Config]]:
    return None  # will be overriden somewhere...


class User(BaseModel):
    id: str


class Action(BaseModel):
    action_id: str
    value: Optional[str]


class CancelBookingActionValue(BaseModel):
    class_id: str
    user_id: str


class InteractionContainer(BaseModel):
    type: str
    message_ts: str


class Interaction(BaseModel):
    type: str
    trigger_id: str
    user: User
    actions: List[Action]
    response_url: str
    container: InteractionContainer


def find_config_by_slack_id(configs: list[Config], user_id: str) -> Optional[Config]:
    for config in configs:
        if config.notifications is None:
            continue
        if config.notifications.slack is None:
            continue
        if config.notifications.slack.user_id == user_id:
            return config
    return None


def deserialize_cancel_booking_action_value(val: str) -> CancelBookingActionValue:
    as_dict = json.loads(val)
    return CancelBookingActionValue(
        user_id=as_dict['userId'],
        class_id=as_dict['classId']
    )


def handle_cancel_booking_slack_action(config: Config, action_value: CancelBookingActionValue, message_ts: str,
                                       response_url: str):
    if config.notifications is None:
        print("[WARNING] Notifications config not specified, no notifications will be sent!")
        slack_config = None
    else:
        slack_config = config.notifications.slack
        if slack_config is None:
            print("[WARNING] Slack notifications config not specified, no Slack notifications will be sent!")
        else:
            notify_working_slack(slack_config.bot_token, slack_config.channel_id, message_ts)
    print("[INFO] Authenticating...")
    auth_result = try_authenticate(config.auth.email, config.auth.password, config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        print("[ERROR] Authentication failed, abort!")
        if slack_config is not None:
            notify_cancellation_failure_slack(slack_config.bot_token, slack_config.channel_id, message_ts, auth_result)
        return
    _class = find_class_by_id(auth_result, action_value.class_id)
    if _class is None:
        print("[ERROR] Class retrieval by id failed, abort!")
        if slack_config is not None:
            notify_cancellation_failure_slack(slack_config.bot_token, slack_config.channel_id, message_ts,
                                              BookingError.CLASS_MISSING)
        return
    cancellation_error = try_cancel_booking(auth_result, _class, config.booking.max_attempts)
    if cancellation_error is not None:
        if slack_config is not None:
            notify_cancellation_failure_slack(slack_config.bot_token, slack_config.channel_id, message_ts,
                                              cancellation_error)
        return
    if slack_config is not None:
        notify_cancellation_slack(slack_config.bot_token, slack_config.channel_id, message_ts, response_url)


def verify_slack_request(body: bytes, headers: Headers, signing_secret: str):
    # see https://api.slack.com/authentication/verifying-requests-from-slack
    return SignatureVerifier(signing_secret=signing_secret).is_valid(
        body,
        headers.get("x-slack-request-timestamp"),
        headers.get("x-slack-signature")
    )


@api.post("/")
async def slack_action(request: Request, background_tasks: BackgroundTasks,
                       configs: Optional[list[Config]] = Depends(get_configs)):
    if configs is None:
        print("[ERROR] No configs available, abort!")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    raw_body = await request.body()  # must read body before retrieving form data
    payload = (await request.form())["payload"]
    interaction: Interaction = pydantic.parse_raw_as(type_=Interaction, b=payload)
    if interaction.type != "block_actions":
        return Response(f"Unsupported interaction type '{interaction.type}'", status_code=status.HTTP_400_BAD_REQUEST)
    if len(interaction.actions) != 1:
        return Response(f"Unsupported number of interaction actions", status_code=status.HTTP_400_BAD_REQUEST)
    action = interaction.actions[0]
    action_value = deserialize_cancel_booking_action_value(action.value)
    if action.action_id == SLACK_ACTION_ADD_BOOKING_TO_CALENDAR:
        return Response(status_code=status.HTTP_200_OK)
    if action.action_id == SLACK_ACTION_CANCEL_BOOKING:
        message_ts = interaction.container.message_ts
        config = find_config_by_slack_id(configs, action_value.user_id)
        if config is None:
            print("[ERROR] Could not find config for Slack user, abort!")
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
        if config.notifications is None \
                or config.notifications.slack is None \
                or not verify_slack_request(raw_body, request.headers, config.notifications.slack.signing_secret):
            return Response(f"Authentication failed", status_code=status.HTTP_401_UNAUTHORIZED)
        # This check should be performed before retrieving config, but then we wouldn't be able to display a funny modal
        if action_value.user_id != interaction.user.id:
            print("[WARNING] Detected cancellation attempt by an unauthorized user")
            if config.notifications is not None and config.notifications.slack is not None:
                background_tasks.add_task(show_unauthorized_action_modal_slack, config.notifications.slack.bot_token,
                                          interaction.trigger_id)
            return Response("Nice try 👏", status_code=status.HTTP_403_FORBIDDEN)
        background_tasks.add_task(handle_cancel_booking_slack_action, config, action_value, message_ts,
                                  interaction.response_url)
        return Response(status_code=status.HTTP_200_OK)
    return Response(f"Unsupported interaction action", status_code=status.HTTP_400_BAD_REQUEST)
