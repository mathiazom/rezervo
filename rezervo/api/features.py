from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.schemas.camel import CamelModel
from rezervo.schemas.config.admin import AdminConfig
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import read_app_config

router = APIRouter()


class Features(CamelModel):
    class_reminder_notifications: bool


@router.get("/features", response_model=Features)
def get_features(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    admin_config = AdminConfig(**db_user.admin_config)
    return Features(
        class_reminder_notifications=(
            admin_config.notifications is not None
            and admin_config.notifications.slack is not None
            and admin_config.notifications.slack.user_id is not None
        ),
    )
