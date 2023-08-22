from auth0.authentication import GetToken
from auth0.management import Auth0

from rezervo.auth.jwt import decode_jwt
from rezervo.settings import Settings, get_settings


def sub_from_jwt(token, domain, algorithms, api_audience, issuer):
    return decode_jwt(token.credentials, domain, algorithms, api_audience, issuer).get(
        "sub", None
    )


def get_auth0_management_client() -> Auth0:
    settings: Settings = get_settings()
    mgmt_api_token = GetToken(
        domain=settings.JWT_DOMAIN,
        client_id=settings.AUTH0_MANAGEMENT_API_CLIENT_ID,
        client_secret=settings.AUTH0_MANAGEMENT_API_CLIENT_SECRET,
    ).client_credentials(audience=f"https://{settings.JWT_DOMAIN}/api/v2/")[
        "access_token"
    ]
    return Auth0(settings.JWT_DOMAIN, mgmt_api_token)
