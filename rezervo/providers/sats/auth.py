from typing import Union

from aiohttp import ClientSession, FormData
from pydantic import ValidationError

from rezervo.errors import AuthenticationError
from rezervo.providers.sats.helpers import retrive_sats_page_props
from rezervo.providers.sats.schema import SatsBookingsResponse
from rezervo.providers.sats.urls import AUTH_URL, BOOKINGS_PATH, LOGIN_PATH
from rezervo.utils.logging_utils import err


async def authenticate_session(
    session: ClientSession, username: str, password: str
) -> Union[ClientSession, AuthenticationError]:
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
        SatsBookingsResponse(**retrive_sats_page_props(str(await auth_res.read())))
        return session
    except ValidationError:
        err.log("Authentication failed")
        return AuthenticationError.INVALID_CREDENTIALS
