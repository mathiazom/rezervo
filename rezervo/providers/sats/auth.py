from typing import Optional, TypeAlias, Union

from aiohttp import ClientSession, FormData
from pydantic import ValidationError

from rezervo.errors import AuthenticationError
from rezervo.http_client import create_tcp_connector
from rezervo.providers.sats.consts import SATS_AUTH_COOKIE_NAME, SATS_REQUEST_HEADERS
from rezervo.providers.sats.helpers import retrieve_sats_page_props
from rezervo.providers.sats.schema import SatsBookingsResponse, SatsMyPageResponse
from rezervo.providers.sats.urls import (
    AUTH_URL,
    BOOKINGS_PATH,
    LOGIN_PATH,
    MY_PAGE_URL,
)
from rezervo.utils.logging_utils import err

SatsAuthData: TypeAlias = str


def create_public_sats_client_session() -> ClientSession:
    return ClientSession(
        connector=create_tcp_connector(),
        headers=SATS_REQUEST_HEADERS,
    )


def create_authed_sats_session(auth_data: SatsAuthData) -> ClientSession:
    return ClientSession(
        connector=create_tcp_connector(),
        cookies={SATS_AUTH_COOKIE_NAME: auth_data},
        headers=SATS_REQUEST_HEADERS,
    )


async def fetch_authed_sats_cookie(
    username: str, password: Optional[str]
) -> Union[SatsAuthData, AuthenticationError]:
    async with create_public_sats_client_session() as session:
        auth_res = await session.post(
            AUTH_URL,
            data=FormData(
                {
                    "user": username,
                    "password": password,
                    "onError": LOGIN_PATH,
                    "onSuccess": BOOKINGS_PATH,
                }
            ),
        )
        try:
            # verify that the response contains user data
            SatsBookingsResponse(
                **(retrieve_sats_page_props(str(await auth_res.read())))
            )
            for cookie in session.cookie_jar:
                if cookie.key == SATS_AUTH_COOKIE_NAME:
                    return cookie.value
            return AuthenticationError.ERROR
        except ValidationError as e:
            err.log("Authentication failed", e)
            return AuthenticationError.INVALID_CREDENTIALS


async def validate_token(
    auth_data: SatsAuthData,
) -> Union[None, AuthenticationError]:
    async with create_authed_sats_session(auth_data) as session:
        async with session.get(MY_PAGE_URL) as my_page_res:
            if not my_page_res.ok:
                err.log("Validation of authentication token failed")
                return AuthenticationError.TOKEN_VALIDATION_FAILED
            try:
                # verify that the response contains some user data
                my_page_data = SatsMyPageResponse(
                    **retrieve_sats_page_props(str(await my_page_res.read()))
                )
                if len("".join(my_page_data.membershipSettings.profile.info)) == 0:
                    return AuthenticationError.TOKEN_INVALID
            except ValidationError:
                return AuthenticationError.TOKEN_INVALID
    return None
