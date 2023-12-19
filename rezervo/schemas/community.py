import enum

from pydantic import BaseModel


class UserRelationship(enum.Enum):
    UNKNOWN = "UNKNOWN"
    REQUEST_SENT = "REQUEST_SENT"
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    FRIEND = "FRIEND"


class CommunityUser(BaseModel):
    name: str
    chains: list[str]
    relationship: UserRelationship


class Community(BaseModel):
    users: list[CommunityUser]
