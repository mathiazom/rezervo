import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from starlette.background import BackgroundTasks

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.chains.active import get_chain
from rezervo.cron import refresh_recurring_booking_cron_jobs
from rezervo.database import crud
from rezervo.providers.ibooking.auth import (
    WAIT_FOR_TOTP_VERIFICATION_MAX_SECONDS,
    WAIT_FOR_TOTP_VERIFICATION_MILLISECONDS,
)
from rezervo.schemas.community import UserRelationship
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import read_app_config
from rezervo.schemas.config.user import (
    BaseChainConfig,
    ChainConfig,
    ChainIdentifier,
    ChainUserCredentials,
    ChainUserProfile,
    ChainUserTOTPPayload,
    InitiatedTOTPFlowResponse,
    PutChainUserCredsResponse,
    UpdatedChainUserCredsResponse,
    UserIdAndNameWithIsSelf,
)
from rezervo.sessions import (
    pull_sessions,
    update_planned_sessions,
)
from rezervo.utils.config_utils import class_config_recurrent_id

router = APIRouter()


@router.get("/{chain_identifier}/user", response_model=ChainUserProfile)
def get_chain_user_profile(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_profile = crud.get_chain_user_profile(db, chain_identifier, db_user.id)
    if user_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user_profile


@router.put("/{chain_identifier}/user", response_model=PutChainUserCredsResponse)
async def put_chain_user_creds(
    chain_identifier: ChainIdentifier,
    chain_user_creds: ChainUserCredentials,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    chain = get_chain(chain_identifier)
    if not await chain.verify_authentication(chain_user_creds):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updated_config = crud.upsert_chain_user_creds(
        db, db_user.id, chain_identifier, chain_user_creds
    )
    if updated_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if chain.totp_enabled:
        background_tasks.add_task(
            chain.initiate_totp_flow, chain.identifier, db_user.id
        )
        return InitiatedTOTPFlowResponse(
            totp_regex=chain.totp_regex,
        )
    background_tasks.add_task(
        refresh_recurring_booking_cron_jobs, db_user.id, [chain_identifier]
    )
    return UpdatedChainUserCredsResponse(
        profile=ChainUserProfile(
            username=updated_config.username, is_auth_verified=True
        )
    )


@router.put("/{chain_identifier}/user/totp")
async def put_chain_user_totp(
    chain_identifier: ChainIdentifier,
    payload: ChainUserTOTPPayload,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    chain = get_chain(chain_identifier)
    if not chain.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    db_chain_user = crud.get_db_chain_user(db, chain_identifier, db_user.id)
    if db_chain_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    totp = payload.totp
    if not await chain.verify_totp(totp):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    verification_timestamp = crud.get_chain_user_auth_verified_at(
        db, db_chain_user.chain, db_chain_user.user_id
    )
    db_chain_user.totp = totp
    db.commit()
    # wait for TOTP to be marked as verified (timestamp is updated)
    wait_start = asyncio.get_event_loop().time()
    while (
        asyncio.get_event_loop().time()
        < wait_start + WAIT_FOR_TOTP_VERIFICATION_MAX_SECONDS
    ):
        current_timestamp = crud.get_chain_user_auth_verified_at(
            db, db_chain_user.chain, db_chain_user.user_id
        )
        if current_timestamp is not None and (
            verification_timestamp is None or verification_timestamp < current_timestamp
        ):
            background_tasks.add_task(
                refresh_recurring_booking_cron_jobs, db_user.id, [chain_identifier]
            )
            return
        await asyncio.sleep(WAIT_FOR_TOTP_VERIFICATION_MILLISECONDS / 1000)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)


@router.get("/{chain_identifier}/config", response_model=BaseChainConfig)
def get_chain_config(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    config = crud.get_chain_config(db, chain_identifier, db_user.id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config


@router.put("/{chain_identifier}/config", response_model=BaseChainConfig)
async def put_chain_config(
    chain_identifier: ChainIdentifier,
    chain_config: BaseChainConfig,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    previous_config = crud.get_chain_config(db, chain_identifier, db_user.id)
    updated_config = crud.update_chain_config(
        db,
        db_user.id,
        ChainConfig(**chain_config.dict(), chain=chain_identifier),
    )
    if updated_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # optimistically update session data, but start proper sync in background
    await update_planned_sessions(
        chain_identifier,
        db_user.id,
        previous_config,
        updated_config,
    )
    background_tasks.add_task(pull_sessions, chain_identifier, db_user.id)
    # TODO: debounce refresh to better handle burst updates
    background_tasks.add_task(
        refresh_recurring_booking_cron_jobs, db_user.id, [chain_identifier]
    )
    return updated_config


@router.get(
    "/{chain_identifier}/all-configs",
    response_model=dict[str, list[UserIdAndNameWithIsSelf]],
)
def get_all_configs_index(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    active_chain_users = crud.get_chain_users(db, chain_identifier, active_only=True)
    user_relationship_index = crud.get_user_relationship_index(db, db_user.id)
    friendly_chain_users = [
        cu
        for cu in active_chain_users
        if cu.user_id == db_user.id
        or user_relationship_index.get(cu.user_id) == UserRelationship.FRIEND
    ]
    user_configs_dict: dict[str, list[UserIdAndNameWithIsSelf]] = {}
    for chain_user in friendly_chain_users:
        dbu = crud.get_user(db, chain_user.user_id)
        if dbu is None:
            continue
        for c in chain_user.recurring_bookings:
            class_id = class_config_recurrent_id(c)
            if class_id not in user_configs_dict:
                user_configs_dict[class_id] = []
            user_configs_dict[class_id].append(
                UserIdAndNameWithIsSelf(
                    is_self=chain_user.user_id == db_user.id,
                    user_id=chain_user.user_id,
                    user_name=dbu.name,
                )
            )
    return user_configs_dict
