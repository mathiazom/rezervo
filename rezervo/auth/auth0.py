from auth0.authentication import GetToken  # type: ignore[import-untyped]
from auth0.management import Auth0  # type: ignore[import-untyped]
from auth0.rest import RestClientOptions  # type: ignore[import-untyped]

from rezervo.auth.jwt import decode_jwt
from rezervo.settings import Settings, get_settings


def sub_from_jwt(token, domain, algorithms, api_audience, issuer):
    return decode_jwt(token.credentials, domain, algorithms, api_audience, issuer).get(
        "sub", None
    )


def get_auth0_management_client() -> Auth0:
    settings: Settings = get_settings()
    domain = settings.JWT_DOMAIN
    client_id = settings.AUTH0_MANAGEMENT_API_CLIENT_ID
    client_secret = settings.AUTH0_MANAGEMENT_API_CLIENT_SECRET
    if domain is None or client_id is None or client_secret is None:
        raise ValueError(
            "Auth0 management API client credentials not configured correctly"
        )
    mgmt_api_token = GetToken(
        domain=domain,
        client_id=client_id,
        client_secret=client_secret,
    ).client_credentials(audience=f"https://{domain}/api/v2/")["access_token"]
    return Auth0(domain, mgmt_api_token, RestClientOptions(timeout=20.0))


def get_auth0_user_name(auth0_mgmt_client: Auth0, jwt_sub: str) -> str:
    return auth0_mgmt_client.users.get(jwt_sub, ["name"])["name"]
