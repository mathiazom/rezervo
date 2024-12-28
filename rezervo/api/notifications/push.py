from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import PushNotificationSubscription, read_app_config

router = APIRouter()


@router.get("/notifications/push/public-key", response_model=str)
def get_push_notifications_public_key(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return app_config.notifications.web_push.public_key


@router.put("/notifications/push", response_model=PushNotificationSubscription)
def subscribe_to_push_notifications(
    subscription: PushNotificationSubscription,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_subscription = crud.upsert_push_notification_subscription(
        db, db_user.id, subscription
    )
    return db_subscription


@router.delete("/notifications/push", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_from_push_notifications(
    subscription: PushNotificationSubscription,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    deleted = crud.delete_push_notification_subscription(db, subscription, db_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return None


@router.post("/notifications/push/verify", response_model=bool)
def verify_push_notifications_subscription(
    subscription: PushNotificationSubscription,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return crud.verify_push_notification_subscription(db, db_user.id, subscription)
