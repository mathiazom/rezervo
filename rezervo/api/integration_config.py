from auth0.management import Auth0
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from starlette.background import BackgroundTasks

from rezervo import models
from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth.auth0 import get_auth0_management_client
from rezervo.cron import refresh_cron
from rezervo.database import crud
from rezervo.schemas.config.user import (
    BaseIntegrationConfig,
    IntegrationConfig,
    IntegrationIdentifier,
    IntegrationUser,
    IntegrationUserCredentials,
    IntegrationUserProfile,
    UserNameWithIsSelf,
)
from rezervo.settings import Settings, get_settings
from rezervo.utils.config_utils import class_config_recurrent_id

router = APIRouter()


@router.get("/{integration}/user", response_model=IntegrationUserProfile)
def get_integration_user_profile(
    integration: IntegrationIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    config_info = crud.get_integration_user_profile(db, integration, db_user.id)
    if config_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config_info


@router.put("/{integration}/user", response_model=IntegrationUserProfile)
def put_integration_user_creds(
    integration: IntegrationIdentifier,
    integration_user_creds: IntegrationUserCredentials,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    updated_config = crud.upsert_integration_user(
        db, db_user.id, integration, integration_user_creds
    )
    if updated_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    background_tasks.add_task(refresh_cron)
    return updated_config


@router.get("/{integration}/config", response_model=IntegrationConfig)
def get_integration_config(
    integration: IntegrationIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    config = crud.get_integration_config(db, integration, db_user.id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config


@router.put("/{integration}/config", response_model=IntegrationConfig)
def put_integration_config(
    integration: IntegrationIdentifier,
    integration_config: BaseIntegrationConfig,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    updated_config = crud.update_integration_config(
        db,
        db_user.id,
        IntegrationConfig(**integration_config.dict(), integration=integration),
    )
    if updated_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    background_tasks.add_task(refresh_cron)
    return updated_config


@router.get(
    "/{integration}/all-configs", response_model=dict[str, list[UserNameWithIsSelf]]
)
def get_all_configs_index(
    integration: IntegrationIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    auth0_mgmt_client: Auth0 = Depends(get_auth0_management_client),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_integration_users = db.query(models.IntegrationUser).filter_by(
        integration=integration, active=True
    )
    user_configs_dict: dict[str, list[UserNameWithIsSelf]] = {}
    for db_integration_user in db_integration_users:
        integration_user = IntegrationUser.from_orm(db_integration_user)
        dbu = crud.get_user(db, integration_user.user_id)
        if dbu is None:
            continue
        name = auth0_mgmt_client.users.get(dbu.jwt_sub)["name"]  # type: ignore[attr-defined]
        for c in integration_user.classes:
            class_id = class_config_recurrent_id(c)
            if class_id not in user_configs_dict:
                user_configs_dict[class_id] = []
            user_configs_dict[class_id].append(
                UserNameWithIsSelf(
                    is_self=integration_user.user_id == db_user.id, user_name=name
                )
            )
    return user_configs_dict
