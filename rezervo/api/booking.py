from apprise import NotifyType
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
from rezervo.models import User
from rezervo.notify.apprise import aprs
from rezervo.schemas.camel import CamelModel
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import ConfigValue, read_app_config
from rezervo.schemas.config.user import ChainIdentifier, ChainUser
from rezervo.sessions import pull_sessions, remove_session, upsert_booked_session
from rezervo.utils.apprise_utils import aprs_ctx
from rezervo.utils.logging_utils import log

router = APIRouter()


def authenticate_chain_user_with_config(
    chain_identifier: ChainIdentifier,
    db: Session,
    app_config: AppConfig,
    token: str,
) -> tuple[User, ChainUser, ConfigValue]:
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    chain_user = crud.get_chain_user(db, chain_identifier, db_user.id)
    if chain_user is None:
        log.warning(f"No '{chain_identifier}' user for given user id")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return db_user, chain_user, crud.get_user_config(db, db_user).config


class BookingPayload(CamelModel):
    class_id: str


@router.post("/{chain_identifier}/book")
async def book_class_api(
    chain_identifier: ChainIdentifier,
    payload: BookingPayload,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    log.debug("Authenticating rezervo user ...")
    user, chain_user, config = authenticate_chain_user_with_config(
        chain_identifier, db, app_config, token
    )
    log.debug("Searching for class...")
    _class = await find_class_by_id(chain_user, payload.class_id)
    match _class:
        case AuthenticationError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to authenticate when booking",
                    body=f"Failed to authenticate '{chain_identifier}' user '{chain_user.username}' for finding class to book manually",
                    attach=[error_ctx],
                )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to find class to book manually",
                    body=f"Failed to find class to book manually for '{chain_identifier}' user '{chain_user.username}'",
                    attach=[error_ctx],
                )
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    log.debug("Authenticating chain user...")
    auth_data = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_data, AuthenticationError):
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Failed to authenticate when booking",
                body=f"Failed to authenticate '{chain_identifier}' user '{chain_user.username}' for class booking",
                attach=[error_ctx],
            )
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    log.debug("Booking class...")
    booking_result = await book_class(
        chain_user.chain,
        auth_data,
        _class,
        config,
        user.id,
    )
    match booking_result:
        case AuthenticationError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to authenticate when booking",
                    body=f"Failed to authenticate '{chain_identifier}' user '{chain_user.username}' for class booking",
                    attach=[error_ctx],
                )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to book class manually",
                    body=f"Failed to book class manually for '{chain_identifier}' user '{chain_user.username}'",
                    attach=[error_ctx],
                )
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # optimistically update session data, but start proper sync in background
    upsert_booked_session(chain_identifier, chain_user.user_id, _class, booking_result)
    background_tasks.add_task(pull_sessions, chain_identifier, chain_user.user_id)


class BookingCancellationPayload(CamelModel):
    class_id: str


@router.post("/{chain_identifier}/cancel-booking")
async def cancel_booking_api(
    chain_identifier: ChainIdentifier,
    payload: BookingCancellationPayload,
    background_tasks: BackgroundTasks,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    log.debug("Authenticating rezervo user...")
    user, chain_user, config = authenticate_chain_user_with_config(
        chain_identifier, db, app_config, token
    )
    log.debug("Searching for class...")
    _class = await find_class_by_id(chain_user, payload.class_id)
    match _class:
        case AuthenticationError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to authenticate when cancelling booking",
                    body=f"Failed to authenticate '{chain_identifier}' user '{chain_user.username}' for finding class to cancel booking manually",
                    attach=[error_ctx],
                )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to find class to cancel booking manually",
                    body=f"Failed to find class to cancel booking manually for '{chain_identifier}' user '{chain_user.username}'",
                    attach=[error_ctx],
                )
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    log.debug("Authenticating chain user...")
    auth_data = await authenticate(chain_user, config.auth.max_attempts)
    if isinstance(auth_data, AuthenticationError):
        with aprs_ctx() as error_ctx:
            aprs.notify(
                notify_type=NotifyType.FAILURE,
                title="Failed to authenticate when cancelling booking",
                body=f"Failed to authenticate '{chain_identifier}' user '{chain_user.username}' for class booking cancellation",
                attach=[error_ctx],
            )
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    log.debug("Cancelling booking...")
    cancellation_res = await cancel_booking(
        chain_user.chain,
        auth_data,
        _class,
        config,
        user.id,
    )
    match cancellation_res:
        case AuthenticationError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to authenticate when cancelling booking",
                    body=f"Failed to authenticate '{chain_identifier}' user '{chain_user.username}' for class booking cancellation",
                    attach=[error_ctx],
                )
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title="Failed to cancel booking manually",
                    body=f"Failed to cancel booking manually for '{chain_identifier}' user '{chain_user.username}'",
                    attach=[error_ctx],
                )
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # optimistically update session data, but start proper sync in background
    await remove_session(chain_identifier, chain_user.user_id, _class.id)
    background_tasks.add_task(pull_sessions, chain_identifier, chain_user.user_id)
