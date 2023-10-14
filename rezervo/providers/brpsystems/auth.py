import re
from typing import Union

import requests
from requests import Session

from rezervo.errors import AuthenticationError
from rezervo.providers.brpsystems.consts import AUTH_URL
from rezervo.providers.brpsystems.schema import BrpAuthResult
from rezervo.utils.logging_utils import err


def authenticate(
    email: str, password: str
) -> Union[BrpAuthResult, AuthenticationError]:
    session = Session()
    auth_res = session.post(
        AUTH_URL,
        json={"username": email, "password": password},
    )
    if auth_res.status_code != requests.codes.OK:
        return AuthenticationError.ERROR
    auth_soup = re.sub(" +", " ", auth_res.text.replace("\n", ""))
    invalid_credentials_matches = re.search(
        r"Feil brukernavn eller passord.", auth_soup
    )
    if invalid_credentials_matches is not None:
        err.log("Authentication failed, invalid credentials")
        return AuthenticationError.INVALID_CREDENTIALS
    return auth_res.json()
