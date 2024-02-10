from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.database.crud import get_user_config_by_id
from rezervo.notify.push import notify_friend_request_web_push
from rezervo.schemas.community import (
    Community,
    UserRelationship,
    UserRelationshipActionPayload,
)
from rezervo.settings import Settings, get_settings

router = APIRouter()


@router.get("/community", response_model=Community)
def get_community(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    users = crud.get_community(db, db_user.id)
    return users


@router.put("/community/update-relationship", response_model=UserRelationship)
def update_relationship(
    payload: UserRelationshipActionPayload,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    updated_relationship = crud.modify_user_relationship(
        db, db_user.id, payload.user_id, payload.action
    )

    if updated_relationship is UserRelationship.REQUEST_SENT:
        receiver_push_subscriptions = get_user_config_by_id(
            db, payload.user_id
        ).config.notifications.push_notification_subscriptions
        if receiver_push_subscriptions is not None:
            for subscription in receiver_push_subscriptions:
                notify_friend_request_web_push(subscription, db_user.name)

    return updated_relationship
