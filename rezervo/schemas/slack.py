from typing import Optional

from pydantic import BaseModel

from rezervo.schemas.config.user import ChainIdentifier


class User(BaseModel):
    id: str


class Action(BaseModel):
    action_id: str
    value: Optional[str]


class CancelBookingActionValue(BaseModel):
    chain_identifier: ChainIdentifier
    class_id: str
    user_id: str
    scheduled_reminder_id: Optional[str] = None


class InteractionContainer(BaseModel):
    type: str
    message_ts: str


class Interaction(BaseModel):
    type: str
    trigger_id: str
    user: User
    actions: list[Action]
    response_url: str
    container: InteractionContainer
