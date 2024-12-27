from apprise import NotifyType
from fastapi import APIRouter, Depends
from starlette import status
from starlette.responses import Response

from rezervo import models
from rezervo.api.common import get_db
from rezervo.cli.fusionauth.consts import (
    FUSIONAUTH_USER_CREATED_EVENT_TYPE,
    FUSIONAUTH_USER_DELETED_EVENT_TYPE,
)
from rezervo.database import crud
from rezervo.notify.apprise import aprs
from rezervo.schemas.camel import CamelModel
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import read_app_config
from rezervo.utils.apprise_utils import aprs_ctx
from rezervo.utils.logging_utils import log

router = APIRouter()


class UserLifecycleEventUser(CamelModel):
    id: str
    username: str


class UserLifecycleEvent(CamelModel):
    user: UserLifecycleEventUser
    type: str


class UserLifecyclePayload(CamelModel):
    event: UserLifecycleEvent


@router.post("/webhooks/user-lifecycle")
async def user_lifecycle(
    payload: UserLifecyclePayload,
    response: Response,
    db=Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    log.debug(
        f"Received webhook user lifecycle event '{payload.event.type}': {payload}"
    )
    event_user = payload.event.user
    if event_user.username == app_config.fusionauth.admin.username:
        log.debug(
            f"User '{event_user.username}' is the admin user, event ignored. \n{payload}"
        )
        return
    if payload.event.type == FUSIONAUTH_USER_CREATED_EVENT_TYPE:
        if (
            db.query(models.User).filter_by(jwt_sub=event_user.id).one_or_none()
            is not None
        ):
            log.info(
                f"User with matching 'jwt_sub' already exists. User creation event ignored. \n{payload}"
            )
            return
        if (
            db.query(models.User).filter_by(name=event_user.username).one_or_none()
            is not None
        ):
            log.error(
                f"User with matching 'name' already exists. User creation event ignored. \n{payload}"
            )
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to create user from webhook event",
                    body=f"User with name '{event_user.username}' already exists. User creation event ignored.",
                    attach=[error_ctx],
                )
            response.status_code = status.HTTP_400_BAD_REQUEST
            return
        db_user = crud.create_user(db, event_user.username, event_user.id)
        log.info(f"User '{db_user.name}' created via webhook event {payload.event}")
        return
    if payload.event.type == FUSIONAUTH_USER_DELETED_EVENT_TYPE:
        user = db.query(models.User).filter_by(jwt_sub=event_user.id).one_or_none()
        if user is None:
            log.debug(f"User not found, delete event ignored. \n{payload}")
            return
        crud.delete_user(db, user.id)
        log.info(f"User '{user.name}' deleted via webhook event {payload.event}")
        return
    response.status_code = status.HTTP_400_BAD_REQUEST
