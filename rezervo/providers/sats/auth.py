from typing import TypeAlias, Union

from aiohttp import ClientSession, FormData
from pydantic import ValidationError

from rezervo.errors import AuthenticationError
from rezervo.http_client import create_client_session, create_tcp_connector
from rezervo.providers.sats.helpers import retrieve_sats_page_props
from rezervo.providers.sats.schema import SatsBookingsResponse
from rezervo.providers.sats.urls import (
    AUTH_URL,
    BOOKINGS_PATH,
    BOOKINGS_URL,
    LOGIN_PATH,
)
from rezervo.utils.logging_utils import err

SatsAuthResult: TypeAlias = str

SATS_AUTH_COOKIE_NAME = ".SATSBETA"


def create_sats_session(auth_result: SatsAuthResult) -> ClientSession:
    return ClientSession(
        connector=create_tcp_connector(), cookies={SATS_AUTH_COOKIE_NAME: auth_result}
    )


async def fetch_authed_sats_cookie(
    username: str, password: str
) -> Union[SatsAuthResult, AuthenticationError]:
    async with create_client_session() as session:
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
            headers={"Accept": "text/html"},
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
    auth_result: SatsAuthResult,
) -> Union[None, AuthenticationError]:
    async with create_sats_session(auth_result) as session:
        async with session.get(
            BOOKINGS_URL, headers={"Accept": "text/html"}
        ) as bookings_res:
            try:
                # verify that the response contains user data
                SatsBookingsResponse(
                    **(retrieve_sats_page_props(str(await bookings_res.read())))
                )
            except ValidationError:
                err.log("Authentication failed")
                return AuthenticationError.TOKEN_INVALID
    return None
