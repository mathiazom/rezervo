import time
from typing import Callable, TypeVar, Union

from rezervo.errors import AuthenticationError
from rezervo.schemas.config.user import IntegrationUser
from rezervo.utils.logging_utils import err

T = TypeVar("T")


def try_authenticate(
    authenticate_fn: Callable[[IntegrationUser], Union[T, AuthenticationError]],
    integration_user: IntegrationUser,
    max_attempts: int,
) -> Union[T, AuthenticationError]:
    if max_attempts < 1:
        return AuthenticationError.ERROR
    success = False
    attempts = 0
    result = None
    while not success:
        result = authenticate_fn(integration_user)
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
    return result
