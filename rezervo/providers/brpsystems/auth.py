import re
from typing import Union

import requests
from aiohttp import ClientSession

from rezervo.errors import AuthenticationError
from rezervo.providers.brpsystems.schema import BrpAuthResult, BrpSubdomain
from rezervo.utils.logging_utils import err


def auth_url(subdomain: BrpSubdomain) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/auth/login"


async def authenticate(
    subdomain: BrpSubdomain, email: str, password: str
) -> Union[BrpAuthResult, AuthenticationError]:
    async with ClientSession() as session:
        async with session.post(
            auth_url(subdomain),
            json={"username": email, "password": password},
        ) as auth_res:
            if auth_res.status != requests.codes.OK:
                return AuthenticationError.ERROR
            auth_soup = re.sub(" +", " ", (await auth_res.text()).replace("\n", ""))
            auth_res_json = await auth_res.json()
    invalid_credentials_matches = re.search(
        r"Feil brukernavn eller passord.", auth_soup
    )
    if invalid_credentials_matches is not None:
        err.log("Authentication failed, invalid credentials")
        return AuthenticationError.INVALID_CREDENTIALS
    return BrpAuthResult(**auth_res_json)
