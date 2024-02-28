from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import Response

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.chains.common import (
    authenticate,
    book_class,
    cancel_booking,
    find_class_by_id,
)
from rezervo.database import crud
from rezervo.errors import AuthenticationError, BookingError
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import ChainIdentifier, ChainUser
from rezervo.sessions import pull_sessions, remove_session, upsert_booked_session
from rezervo.settings import Settings, get_settings
from rezervo.utils.logging_utils import err

router = APIRouter()


def authenticate_chain_user_with_config(
    chain_identifier: ChainIdentifier,
    db: Session,
    settings: Settings,
    token: str,
) -> tuple[ChainUser, ConfigValue]:
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    chain_user = crud.get_chain_user(db, chain_identifier, db_user.id)
    if chain_user is None:
        err.log(f"No '{chain_identifier}' user for given user id")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return chain_user, crud.get_user_config(db, db_user).config


class BookingPayload(BaseModel):
    class_id: str


@router.post("/{chain_identifier}/book")
async def book_class_api(
    chain_identifier: ChainIdentifier,
    payload: BookingPayload,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    print("Authenticating rezervo user...")
    chain_user, config = authenticate_chain_user_with_config(
        chain_identifier, db, settings, token
    )
    print("Searching for class...")
    _class = await find_class_by_id(chain_user, payload.class_id)
    match _class:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    print("Authenticating chain user...")
    auth_result = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    print("Booking class...")
    booking_result = await book_class(chain_user.chain, auth_result, _class, config)
    match booking_result:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # optimistically update session data, but start proper sync in background
    await upsert_booked_session(chain_identifier, chain_user.user_id, _class)
    background_tasks.add_task(pull_sessions, chain_identifier, chain_user.user_id)


class BookingCancellationPayload(BaseModel):
    class_id: str


@router.post("/{chain_identifier}/cancel-booking")
async def cancel_booking_api(
    chain_identifier: ChainIdentifier,
    payload: BookingCancellationPayload,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    print("Authenticating rezervo user...")
    chain_user, config = authenticate_chain_user_with_config(
        chain_identifier, db, settings, token
    )
    print("Searching for class...")
    _class = await find_class_by_id(chain_user, payload.class_id)
    match _class:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    print("Authenticating chain user...")
    auth_result = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    print("Cancelling booking...")
    cancellation_res = await cancel_booking(
        chain_user.chain, auth_result, _class, config
    )
    match cancellation_res:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # optimistically update session data, but start proper sync in background
    await remove_session(chain_identifier, chain_user.user_id, _class.id)
    background_tasks.add_task(pull_sessions, chain_identifier, chain_user.user_id)
