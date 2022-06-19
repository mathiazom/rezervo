import re
from enum import Enum, auto
from typing import Optional, Union, Tuple

import requests
from requests import Session

from consts import AUTH_URL, BOOKING_URL, TOKEN_VALIDATION_URL

USER_AGENT = "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"


class AuthenticationError(Enum):
    ERROR = auto()
    TOKEN_EXTRACTION_FAILED = auto()
    TOKEN_VALIDATION_FAILED = auto()
    AUTH_TEMPORARILY_BLOCKED = auto()
    INVALID_CREDENTIALS = auto()


def authenticate(email: str, password: str) -> Union[str, AuthenticationError]:
    session = Session()
    user_agent_header = {'User-Agent': USER_AGENT}
    auth_res = session.post(AUTH_URL, {
        "name": email,
        "pass": password,
        "form_id": "user_login"
    }, headers=user_agent_header)
    auth_soup = re.sub(" +", " ", auth_res.text.replace("\n", ""))
    login_blocked_matches = re.search(r"Feilmelding.*?midlertidig blokkert", auth_soup)
    if login_blocked_matches is not None:
        print("[ERROR] Authentication failed, authentication temporarily blocked")
        return AuthenticationError.AUTH_TEMPORARILY_BLOCKED
    invalid_credentials_matches = re.search(r"Feilmelding.*?ukjent brukernavn eller passord", auth_soup)
    if invalid_credentials_matches is not None:
        print("[ERROR] Authentication failed, invalid credentials")
        return AuthenticationError.INVALID_CREDENTIALS
    booking_res = session.get(BOOKING_URL, headers=user_agent_header)
    booking_soup = re.sub(" +", " ", booking_res.text.replace("\n", ""))
    cdata_token_matches = re.search(r"<!\[CDATA\[.*?iBookingPreload\(.*?token:.*?\"(.+?)\".*?]]>", booking_soup)
    if cdata_token_matches is None:
        print("[ERROR] Failed to extract authentication token!")
        return AuthenticationError.TOKEN_EXTRACTION_FAILED
    try:
        token = cdata_token_matches.group(1)
    except IndexError:
        print("[ERROR] Failed to extract authentication token!")
        return AuthenticationError.TOKEN_EXTRACTION_FAILED
    # Validate token
    token_validation = session.post(TOKEN_VALIDATION_URL, {"token": token})
    if token_validation.status_code != requests.codes.OK:
        print("[ERROR] Validation of authentication token failed")
        return AuthenticationError.TOKEN_VALIDATION_FAILED
    token_info = token_validation.json()
    if 'info' in token_info and token_info['info'] == "client-readonly":
        print("[ERROR] Authentication failed, only acquired public readonly access")
        return AuthenticationError.ERROR
    user = token_info['user']
    print(f"[INFO] Authenticated as {user['firstname']} {user['lastname']} ({user['email']})")
    return token
