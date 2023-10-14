from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import Response

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.errors import AuthenticationError, BookingError
from rezervo.providers.common import (
    book_class,
    cancel_booking,
    find_authed_class_by_id,
)
from rezervo.schemas.booking import BookingCancellationPayload, BookingPayload
from rezervo.schemas.config.user import IntegrationIdentifier
from rezervo.sessions import pull_sessions
from rezervo.settings import Settings, get_settings
from rezervo.utils.logging_utils import err

router = APIRouter()


@router.post("/{integration}/book")
def book_class_api(
    integration: IntegrationIdentifier,
    payload: BookingPayload,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    print("Authenticating rezervo user...")
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    integration_user = crud.get_integration_user(db, integration, db_user.id)
    if integration_user is None:
        err.log(f"No {integration} user for given user id, aborted booking.")
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    config = crud.get_user_config(db, db_user).config
    print("Searching for class...")
    _class = find_authed_class_by_id(integration_user, config, payload.class_id)
    match _class:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    print("Booking class...")
    booking_result = book_class(integration_user, _class, config)
    match booking_result:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # Pulling in foreground to have sessions up-to-date once the response is sent
    pull_sessions(integration, db_user.id)


@router.post("/{integration}/cancel-booking")
def cancel_booking_api(
    integration: IntegrationIdentifier,
    payload: BookingCancellationPayload,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    print("Authenticating rezervo user...")
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    integration_user = crud.get_integration_user(db, integration, db_user.id)
    if integration_user is None:
        err.log(f"No {integration} user for given user id, aborted booking.")
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    config = crud.get_user_config(db, db_user).config
    print("Searching for class...")
    _class = find_authed_class_by_id(integration_user, config, payload.class_id)
    match _class:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    print("Cancelling booking...")
    cancellation_res = cancel_booking(integration_user, _class, config)
    match cancellation_res:
        case AuthenticationError():
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        case BookingError():
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # Pulling in foreground to have sessions up-to-date once the response is sent
    pull_sessions(integration, db_user.id)
