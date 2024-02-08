from auth0.management import Auth0
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from starlette.background import BackgroundTasks

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth.auth0 import get_auth0_management_client
from rezervo.chains.active import get_chain
from rezervo.cron import refresh_cron
from rezervo.database import crud
from rezervo.schemas.config.user import (
    BaseChainConfig,
    ChainConfig,
    ChainIdentifier,
    ChainUserCredentials,
    ChainUserProfile,
    UserNameWithIsSelf,
)
from rezervo.settings import Settings, get_settings
from rezervo.utils.config_utils import class_config_recurrent_id

router = APIRouter()


@router.get("/{chain_identifier}/user", response_model=ChainUserProfile)
def get_chain_user_profile(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    config_info = crud.get_chain_user_profile(db, chain_identifier, db_user.id)
    if config_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config_info


@router.put("/{chain_identifier}/user", response_model=ChainUserProfile)
async def put_chain_user_creds(
    chain_identifier: ChainIdentifier,
    chain_user_creds: ChainUserCredentials,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not await get_chain(chain_identifier).verify_authentication(chain_user_creds):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updated_config = crud.upsert_chain_user_creds(
        db, db_user.id, chain_identifier, chain_user_creds
    )
    if updated_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    background_tasks.add_task(refresh_cron, db_user.id, [chain_identifier])
    return {"username": updated_config.username}


@router.get("/{chain_identifier}/config", response_model=BaseChainConfig)
def get_chain_config(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    config = crud.get_chain_config(db, chain_identifier, db_user.id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config


@router.put("/{chain_identifier}/config", response_model=BaseChainConfig)
def put_chain_config(
    chain_identifier: ChainIdentifier,
    chain_config: BaseChainConfig,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    updated_config = crud.update_chain_config(
        db,
        db_user.id,
        ChainConfig(**chain_config.dict(), chain=chain_identifier),
    )
    if updated_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # TODO: debounce refresh to better handle burst updates
    background_tasks.add_task(refresh_cron, db_user.id, [chain_identifier])
    return updated_config


@router.get(
    "/{chain_identifier}/all-configs",
    response_model=dict[str, list[UserNameWithIsSelf]],
)
def get_all_configs_index(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    auth0_mgmt_client: Auth0 = Depends(get_auth0_management_client),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    active_chain_users = crud.get_chain_users(db, chain_identifier, active_only=True)
    user_configs_dict: dict[str, list[UserNameWithIsSelf]] = {}
    for chain_user in active_chain_users:
        dbu = crud.get_user(db, chain_user.user_id)
        if dbu is None:
            continue
        name = auth0_mgmt_client.users.get(dbu.jwt_sub)["name"]  # type: ignore[attr-defined]
        for c in chain_user.recurring_bookings:
            class_id = class_config_recurrent_id(c)
            if class_id not in user_configs_dict:
                user_configs_dict[class_id] = []
            user_configs_dict[class_id].append(
                UserNameWithIsSelf(
                    is_self=chain_user.user_id == db_user.id, user_name=name
                )
            )
    return user_configs_dict
