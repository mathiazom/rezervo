import json
from typing import List, Optional

import pydantic
from fastapi import FastAPI, status, Response, Form
from pydantic import BaseModel

from consts import SLACK_ACTION_ADD_BOOKING_TO_CALENDAR, SLACK_ACTION_CANCEL_BOOKING

app = FastAPI()


class User(BaseModel):
    id: str


class Action(BaseModel):
    action_id: str
    value: Optional[str]


class CancelBookingActionValue(BaseModel):
    class_id: str
    user_id: str


class Interaction(BaseModel):
    type: str
    user: User
    actions: List[Action]


@app.post("/")
def message_interaction(payload: str = Form()):
    interaction = pydantic.parse_raw_as(type_=Interaction, b=payload)
    if interaction.type != "block_actions":
        return Response(f"Unsupported interaction type '{interaction.type}'", status_code=status.HTTP_400_BAD_REQUEST)
    if len(interaction.actions) != 1:
        return Response(f"Unsupported number of interaction actions", status_code=status.HTTP_400_BAD_REQUEST)
    action = interaction.actions[0]
    if action.action_id == SLACK_ACTION_ADD_BOOKING_TO_CALENDAR:
        return Response(status_code=status.HTTP_200_OK)
    if action.action_id == SLACK_ACTION_CANCEL_BOOKING:
        return handle_cancel_booking_action(interaction)
    return Response(f"Unsupported interaction action", status_code=status.HTTP_400_BAD_REQUEST)


def handle_cancel_booking_action(interaction: Interaction):
    action = interaction.actions[0]
    action_value = deserialize_cancel_booking_action_value(action.value)
    if action_value.user_id != interaction.user.id:
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    # TODO: Implement booking cancellation
    return Response(f"Booking cancellation is not supported yet...", status_code=status.HTTP_400_BAD_REQUEST)


def deserialize_cancel_booking_action_value(val: str) -> CancelBookingActionValue:
    as_dict = json.loads(val)
    return CancelBookingActionValue(
        user_id=as_dict['userId'],
        class_id=as_dict['classId']
    )
