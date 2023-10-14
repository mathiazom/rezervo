from typing import Any, Callable, Optional, Union
from uuid import UUID

from pydantic import BaseModel

from rezervo.errors import AuthenticationError, BookingError
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import Class, IntegrationUser
from rezervo.schemas.schedule import RezervoClass, UserSession


class Provider(BaseModel):
    find_authed_class_by_id: Callable[
        [IntegrationUser, ConfigValue, str],
        Union[RezervoClass, BookingError, AuthenticationError],
    ]
    find_class: Callable[
        [Class], Union[RezervoClass, BookingError, AuthenticationError]
    ]
    book_class: Callable[
        [IntegrationUser, RezervoClass, ConfigValue],
        Union[None, BookingError, AuthenticationError],
    ]
    cancel_booking: Callable[
        [IntegrationUser, RezervoClass, ConfigValue],
        Union[None, BookingError, AuthenticationError],
    ]
    fetch_sessions: Callable[[Optional[UUID]], dict[UUID, list[UserSession]]]
    rezervo_class_from_class_data: Callable[[Any], Optional[RezervoClass]]
