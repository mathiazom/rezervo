import re
import time
from typing import Optional, Union

import requests
from requests import Session

from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError
from rezervo.providers.ibooking.consts import AUTH_URL, BOOKING_URL, TOKEN_VALIDATION_URL
from rezervo.schemas.config.user import IntegrationUser
from rezervo.utils.logging_utils import err, warn

USER_AGENT = (
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"
)


def fetch_public_token() -> Union[str, AuthenticationError]:
    # use an unauthenticated session
    return extract_token_from_session(Session())


def authenticate_session(
    email: str, password: str
) -> Union[Session, AuthenticationError]:
    # TODO: inject existing token if valid
    session = Session()
    auth_res = session.post(
        AUTH_URL,
        {"name": email, "pass": password, "form_id": "user_login"},
        headers={"User-Agent": USER_AGENT},
    )
    auth_soup = re.sub(" +", " ", auth_res.text.replace("\n", ""))
    login_blocked_matches = re.search(r"Feilmelding.*?midlertidig blokkert", auth_soup)
    if login_blocked_matches is not None:
        err.log("Authentication failed, authentication temporarily blocked")
        return AuthenticationError.AUTH_TEMPORARILY_BLOCKED
    invalid_credentials_matches = re.search(
        r"Feilmelding.*?ukjent brukernavn eller passord", auth_soup
    )
    if invalid_credentials_matches is not None:
        err.log("Authentication failed, invalid credentials")
        return AuthenticationError.INVALID_CREDENTIALS
    return session


def authenticate_token(
    integration_user: IntegrationUser,
) -> Union[str, AuthenticationError]:
    if integration_user.auth_token is not None:
        validation_error = validate_token(integration_user.auth_token)
        if validation_error is None:
            return integration_user.auth_token
        warn.log("Authentication token validation failed, retrieving fresh token...")
    result = authenticate_session(integration_user.username, integration_user.password)
    if isinstance(result, AuthenticationError):
        return result
    token_res = extract_token_from_session(result)
    if isinstance(token_res, AuthenticationError):
        err.log("Failed to extract authentication token!")
        return token_res
    validation_error = validate_token(token_res)
    if validation_error is not None:
        return validation_error
    return token_res


def validate_token(token: str) -> Optional[AuthenticationError]:
    token_validation = requests.post(TOKEN_VALIDATION_URL, {"token": token})
    if token_validation.status_code != requests.codes.OK:
        if token_validation.status_code != requests.codes.FORBIDDEN:
            err.log("Validation of authentication token failed")
            return AuthenticationError.TOKEN_VALIDATION_FAILED
        return AuthenticationError.TOKEN_INVALID
    token_info = token_validation.json()
    if "info" in token_info and token_info["info"] == "client-readonly":
        err.log("Authentication failed, only acquired public readonly access")
        return AuthenticationError.TOKEN_INVALID
    user = token_info["user"]
    print(f"Authenticated as {user['firstname']} {user['lastname']} ({user['email']})")
    return None


def extract_token_from_session(session: Session) -> Union[str, AuthenticationError]:
    booking_res = session.get(BOOKING_URL, headers={"User-Agent": USER_AGENT})
    booking_soup = re.sub(" +", " ", booking_res.text.replace("\n", ""))
    cdata_token_matches = re.search(
        r"<!\[CDATA\[.*?iBookingPreload\(.*?token:.*?\"(.+?)\".*?]]>", booking_soup
    )
    if cdata_token_matches is None:
        return AuthenticationError.TOKEN_EXTRACTION_FAILED
    try:
        return cdata_token_matches.group(1)
    except IndexError:
        return AuthenticationError.TOKEN_EXTRACTION_FAILED


def try_authenticate(
    integration_user: IntegrationUser, max_attempts: int
) -> Union[str, AuthenticationError]:
    if max_attempts < 1:
        return AuthenticationError.ERROR
    success = False
    attempts = 0
    result = None
    while not success:
        result = authenticate_token(integration_user)
        success = not isinstance(result, AuthenticationError)
        attempts += 1
        if success:
            break
        if result == AuthenticationError.INVALID_CREDENTIALS:
            err.log("Invalid credentials, aborting authentication to avoid lockout")
            break
        if result == AuthenticationError.AUTH_TEMPORARILY_BLOCKED:
            err.log("Authentication temporarily blocked, aborting")
            break
        if attempts >= max_attempts:
            break
        sleep_seconds = 2**attempts
        print(f"Exponential backoff, retrying in {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
    if not success:
        err.log(
            f"Authentication failed after {attempts} attempt"
            + ("s" if attempts != 1 else "")
        )
        return result
    if result is None:
        return AuthenticationError.ERROR
    with SessionLocal() as db:
        crud.upsert_integration_user_token(
            db, integration_user.user_id, integration_user.integration, result
        )
    return result
