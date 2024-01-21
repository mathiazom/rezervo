import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, Optional, Union

from rezervo.consts import PLANNED_SESSIONS_NEXT_WHOLE_WEEKS
from rezervo.errors import AuthenticationError, BookingError
from rezervo.models import SessionState
from rezervo.notify.notify import notify_booking
from rezervo.providers.schema import (
    AuthResult,
    Branch,
    LocationIdentifier,
    LocationProviderIdentifier,
)
from rezervo.providers.sessions import get_user_planned_sessions_from_schedule
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import (
    ChainUser,
    Class,
    config_from_chain_user,
)
from rezervo.schemas.schedule import RezervoClass, RezervoSchedule, UserSession
from rezervo.utils.logging_utils import err
from rezervo.utils.time_utils import (
    first_date_of_week_by_offset,
    total_days_for_next_whole_weeks,
)


class Provider(ABC, Generic[AuthResult, LocationProviderIdentifier]):
    @property
    @abstractmethod
    def branches(self) -> list[Branch[LocationProviderIdentifier]]:
        raise NotImplementedError()

    def locations(self) -> list[LocationIdentifier]:
        return [
            location.identifier
            for branch in self.branches
            for location in branch.locations
        ]

    def provider_location_identifier_from_location_identifier(
        self, location_identifier: LocationIdentifier
    ) -> Optional[LocationProviderIdentifier]:
        for branch in self.branches:
            for location in branch.locations:
                if location.identifier == location_identifier:
                    return location.provider_identifier
        return None

    def location_from_provider_location_identifier(
        self, provider_identifier: LocationProviderIdentifier
    ) -> Optional[LocationIdentifier]:
        for branch in self.branches:
            for location in branch.locations:
                if location.provider_identifier == provider_identifier:
                    return location.identifier
        return None

    @abstractmethod
    def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[AuthResult, AuthenticationError]:
        raise NotImplementedError()

    def try_authenticate(
        self,
        chain_user: ChainUser,
        max_attempts: int,
    ) -> Union[AuthResult, AuthenticationError]:
        if max_attempts < 1:
            return AuthenticationError.ERROR
        success = False
        attempts = 0
        result = None
        while not success:
            result = self._authenticate(chain_user)
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
        if result is None:
            return AuthenticationError.ERROR
        return result

    @abstractmethod
    def find_class_by_id(
        self,
        class_id: str,
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        raise NotImplementedError()

    @abstractmethod
    async def find_class(
        self, _class_config: Class
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        # TODO: unified implementation using `find_class_in_schedule_by_config`
        raise NotImplementedError()

    @abstractmethod
    def _book_class(
        self,
        auth_result: AuthResult,
        class_id: str,
    ) -> bool:
        raise NotImplementedError()

    def try_book_class(
        self, chain_user: ChainUser, _class: RezervoClass, config: ConfigValue
    ) -> Union[None, BookingError, AuthenticationError]:
        max_attempts = config.booking.max_attempts
        if max_attempts < 1:
            err.log("Max booking attempts should be a positive number")
            return BookingError.INVALID_CONFIG
        print("Authenticating...")
        auth_result = self.try_authenticate(chain_user, config.auth.max_attempts)
        if isinstance(auth_result, AuthenticationError):
            err.log("Authentication failed")
            return auth_result
        token = auth_result
        booked = False
        attempts = 0
        while not booked:
            booked = self._book_class(token, _class.id)
            attempts += 1
            if booked:
                break
            if attempts >= max_attempts:
                break
            sleep_seconds = 2**attempts
            print(f"Exponential backoff, retrying in {sleep_seconds} seconds...")
            time.sleep(sleep_seconds)
        if not booked:
            err.log(
                f"Booking failed after {attempts} attempt"
                + ("s" if attempts != 1 else "")
            )
            return BookingError.ERROR
        print(
            "Successfully booked class"
            + (f" after {attempts} attempts!" if attempts != 1 else "!")
        )
        if config.notifications:
            # ical_url = f"{ICAL_URL}/?id={_class.id}&token={token}"    # TODO: consider re-introducing ical
            notify_booking(config.notifications, chain_user.chain, _class)
        return None

    @abstractmethod
    def _cancel_booking(
        self,
        auth_result: AuthResult,
        class_id: str,
    ) -> bool:
        raise NotImplementedError()

    def try_cancel_booking(
        self,
        chain_user: ChainUser,
        _class: RezervoClass,
        config: ConfigValue,
    ) -> Union[None, BookingError, AuthenticationError]:
        if config.booking.max_attempts < 1:
            err.log("Max booking cancellation attempts should be a positive number")
            return BookingError.INVALID_CONFIG
        print("Authenticating...")
        auth_result = self.try_authenticate(chain_user, config.auth.max_attempts)
        if isinstance(auth_result, AuthenticationError):
            err.log("Authentication failed")
            return auth_result
        token = auth_result
        cancelled = False
        attempts = 0
        while not cancelled:
            cancelled = self._cancel_booking(token, _class.id)
            attempts += 1
            if cancelled:
                break
            if attempts >= config.booking.max_attempts:
                break
            sleep_seconds = 2**attempts
            print(f"Exponential backoff, retrying in {sleep_seconds} seconds...")
            time.sleep(sleep_seconds)
        if not cancelled:
            err.log(
                f"Booking cancellation failed after {attempts} attempt"
                + ("s" if attempts != 1 else "")
            )
            return BookingError.ERROR
        print(
            "Successfully cancelled booking"
            + (f" after {attempts} attempts!" if attempts != 1 else "!")
        )
        return None

    async def fetch_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> list[UserSession]:
        schedule = await self.fetch_schedule(
            datetime.combine(datetime.now(), datetime.min.time()),
            total_days_for_next_whole_weeks(PLANNED_SESSIONS_NEXT_WHOLE_WEEKS),
            locations if locations is not None else self.locations(),
        )
        planned_sessions = self.fetch_planned_sessions(chain_user, schedule)
        past_and_booked_sessions = self._fetch_past_and_booked_sessions(
            chain_user, locations
        )
        if past_and_booked_sessions is None:
            return planned_sessions
        sessions_by_class_id = {s.class_id: s for s in planned_sessions}
        for session in past_and_booked_sessions:
            if session.class_id not in sessions_by_class_id:
                sessions_by_class_id[session.class_id] = session
        return list(sessions_by_class_id.values())

    def fetch_planned_sessions(
        self,
        chain_user: ChainUser,
        schedule: RezervoSchedule,
    ) -> list[UserSession]:
        planned_classes = get_user_planned_sessions_from_schedule(
            config_from_chain_user(chain_user),
            schedule,
        )
        return [
            UserSession(
                chain=chain_user.chain,
                class_id=str(p.id),
                user_id=chain_user.user_id,
                status=SessionState.PLANNED,
                class_data=p,
            )
            for p in planned_classes
        ]

    @abstractmethod
    def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> Optional[list[UserSession]]:
        raise NotImplementedError()

    @abstractmethod
    async def fetch_schedule(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        raise NotImplementedError()

    async def fetch_week_schedule(
        self,
        week_offset: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        return await self.fetch_schedule(
            first_date_of_week_by_offset(week_offset), 7, locations
        )
