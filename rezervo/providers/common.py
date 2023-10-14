from typing import Any, Optional, Union

from rezervo.active_integrations import get_integration
from rezervo.errors import AuthenticationError, BookingError
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import Class, IntegrationIdentifier, IntegrationUser
from rezervo.schemas.schedule import RezervoClass


def find_authed_class_by_id(
    integration_user: IntegrationUser, config: ConfigValue, class_id: str
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    return get_integration(integration_user.integration).find_authed_class_by_id(
        integration_user, config, class_id
    )


def find_class(
    integration: IntegrationIdentifier, _class_config: Class
) -> Union[RezervoClass, BookingError, AuthenticationError]:
    return get_integration(integration).find_class(_class_config)


def book_class(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    return get_integration(integration_user.integration).book_class(
        integration_user, _class, config
    )


def cancel_booking(
    integration_user: IntegrationUser, _class: RezervoClass, config: ConfigValue
) -> Union[None, BookingError, AuthenticationError]:
    # TODO: add Slack notifications
    return get_integration(integration_user.integration).cancel_booking(
        integration_user, _class, config
    )


def rezervo_class_from_integration_class_data(
    class_data: Any,
) -> Optional[RezervoClass]:
    return get_integration(class_data.integration).rezervo_class_from_class_data(
        class_data
    )
