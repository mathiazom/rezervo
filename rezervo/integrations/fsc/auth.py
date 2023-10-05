import re
from typing import Union

import requests
from requests import Session

from rezervo.errors import AuthenticationError
from rezervo.integrations.fsc.consts import AUTH_URL, USER_DETAILS_URL
from rezervo.integrations.fsc.schema import UserDetails, UserDetailsResponse
from rezervo.utils.logging_utils import err


def authenticate_session(
    email: str, password: str
) -> Union[Session, AuthenticationError]:
    session = Session()
    auth_res = session.post(
        AUTH_URL,
        {"username": email, "password": password},
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
    return session


def fetch_user_details(
    auth_session: Session,
) -> Union[UserDetails, AuthenticationError]:
    try:
        res = auth_session.get(USER_DETAILS_URL)
    except requests.exceptions.RequestException:
        err.log(
            f"Failed to retrieve user details for '{auth_session}'",
        )
        return AuthenticationError.ERROR
    userDetailsResponse: UserDetailsResponse = res.json()
    return userDetailsResponse["data"]
