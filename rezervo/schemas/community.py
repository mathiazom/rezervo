import enum
from uuid import UUID

from pydantic import BaseModel

from rezervo.schemas.camel import CamelModel


class UserRelationship(enum.Enum):
    UNKNOWN = "UNKNOWN"
    REQUEST_SENT = "REQUEST_SENT"
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    FRIEND = "FRIEND"


class UserRelationshipAction(str, enum.Enum):
    ADD_FRIEND = "ADD_FRIEND"
    ACCEPT_FRIEND = "ACCEPT_FRIEND"
    DENY_FRIEND = "DENY_FRIEND"
    REMOVE_FRIEND = "REMOVE_FRIEND"


class UserRelationshipActionPayload(CamelModel):
    user_id: UUID
    action: UserRelationshipAction


class CommunityUser(CamelModel):
    user_id: UUID
    name: str
    chains: list[str]
    relationship: UserRelationship


class Community(BaseModel):
    users: list[CommunityUser]
