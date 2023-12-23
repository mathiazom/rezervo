from rezervo.errors import AuthenticationError
from rezervo.providers.brpsystems.auth import authenticate
from rezervo.providers.brpsystems.booking import (
    find_brp_class_by_id,
    try_book_brp_class,
    try_cancel_brp_booking,
    try_find_brp_class,
)
from rezervo.providers.brpsystems.schema import (
    BrpSubdomain,
    rezervo_class_from_brp_class,
)
from rezervo.providers.brpsystems.sessions import fetch_brp_sessions
from rezervo.providers.provider import Provider


def get_brp_provider(subdomain: BrpSubdomain, business_unit: int):
    return Provider(
        find_authed_class_by_id=lambda integration_user, config, class_id: find_brp_class_by_id(
            subdomain, business_unit, class_id
        ),
        find_class=lambda class_config: try_find_brp_class(
            subdomain, business_unit, class_config
        ),
        book_class=lambda integration_user, _class, config: try_book_brp_class(
            subdomain, integration_user, _class, config
        ),
        cancel_booking=lambda integration_user, _class, config: try_cancel_brp_booking(
            subdomain, integration_user, _class, config
        ),
        fetch_sessions=lambda user_id: fetch_brp_sessions(
            subdomain, business_unit, user_id
        ),
        rezervo_class_from_class_data=lambda brp_class: rezervo_class_from_brp_class(
            subdomain, brp_class
        ),
        verify_authentication=lambda credentials: not isinstance(
            authenticate(subdomain, credentials.username, credentials.password),
            AuthenticationError,
        ),
    )
