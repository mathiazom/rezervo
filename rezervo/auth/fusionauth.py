from functools import lru_cache

from fusionauth.fusionauth_client import (  # type: ignore[import-untyped]
    FusionAuthClient,
)

from rezervo.schemas.config.config import read_app_config
from rezervo.settings import get_settings


@lru_cache()
def get_fusionauth_client():
    return FusionAuthClient(
        get_settings().FUSIONAUTH_API_KEY, read_app_config().fusionauth.internal_url
    )


@lru_cache()
def get_jwt_public_key():
    res = get_fusionauth_client().retrieve_jwt_public_key_by_application_id(
        read_app_config().fusionauth.application_id
    )
    if res.was_successful():
        return res.success_response.get("publicKey")
    return None


def retrieve_username_by_user_id(user_id):
    res = get_fusionauth_client().retrieve_user(user_id)
    if res.was_successful():
        user = res.success_response.get("user")
        if user is not None:
            return user.get("username")
    return None
