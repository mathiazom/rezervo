import re
from typing import Union

from enum import Enum, auto
from requests import Session

USER_AGENT = "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"


class AuthenticationError(Enum):
    ERROR = auto()
    TOKEN_EXTRACTION_FAILED = auto()
    USER_ID_EXTRACTION_FAILED = auto()
    TOKEN_VALIDATION_FAILED = auto()
    AUTH_TEMPORARILY_BLOCKED = auto()
    INVALID_CREDENTIALS = auto()


def fsc_authenticate(email: str, password: str) -> Union[tuple[str, Session], AuthenticationError]:
    session = Session()
    user_agent_header = {'User-Agent': USER_AGENT}
    auth_res = session.post("https://fsc.no/api/v1/auth/login", {
        "username": email,
        "password": password,
    }, headers=user_agent_header)
    auth_soup = re.sub(" +", " ", auth_res.text.replace("\n", ""))
    invalid_credentials_matches = re.search(r"Feil brukernavn eller passord.", auth_soup)
    if invalid_credentials_matches is not None:
        print("[ERROR] Authentication failed, invalid credentials")
        return AuthenticationError.INVALID_CREDENTIALS

    try:
        token = auth_res.cookies["token"]
    except IndexError:
        print("[ERROR] Failed to extract authentication token!")
        return AuthenticationError.TOKEN_EXTRACTION_FAILED

    res = session.get("https://fsc.no/api/v1/auth/me").json()

    if not res["success"] or not res["data"]["email"]:
        print("[ERROR] Authentication failed, could not get /me")
        return AuthenticationError.ERROR
    print(f"[INFO] Authenticated as {res['data']['firstName']} {res['data']['lastName']} ({res['data']['email']})")
    return token, session
