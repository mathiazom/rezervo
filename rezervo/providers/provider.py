import asyncio
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, Optional, Union
from uuid import UUID

import pytz
from apprise import NotifyType

from rezervo.consts import (
    BOOKING_INITIAL_BURST_ATTEMPTS,
    PLANNED_SESSIONS_NEXT_WHOLE_WEEKS,
)
from rezervo.errors import AuthenticationError, BookingError
from rezervo.models import SessionState
from rezervo.notify.apprise import aprs
from rezervo.notify.notify import (
    notify_booking,
    notify_class_friends_of_booking,
    notify_class_friends_of_cancellation,
)
from rezervo.providers.schema import (
    AuthData,
    Branch,
    LocationIdentifier,
    LocationProviderIdentifier,
)
from rezervo.providers.sessions import get_user_planned_sessions_from_schedule
from rezervo.schemas.config.config import ConfigValue
from rezervo.schemas.config.user import (
    ChainIdentifier,
    ChainUser,
    ChainUserCredentials,
    Class,
    config_from_chain_user,
)
from rezervo.schemas.schedule import (
    BookingResult,
    RezervoClass,
    RezervoSchedule,
    SessionRezervoClass,
    UserSession,
)
from rezervo.utils.logging_utils import log
from rezervo.utils.time_utils import (
    from_compact_iso_week,
    total_days_for_next_whole_weeks,
)


class Provider(ABC, Generic[AuthData, LocationProviderIdentifier]):
    @property
    def totp_enabled(self) -> bool:
        return False

    @property
    def totp_regex(self) -> Optional[str]:
        return None

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
    async def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[AuthData, AuthenticationError]:
        raise NotImplementedError()

    async def extend_auth_session(self, chain_user: ChainUser) -> None:
        pass

    async def try_authenticate(
        self,
        chain_user: ChainUser,
        max_attempts: int,
    ) -> Union[AuthData, AuthenticationError]:
        if max_attempts < 1:
            return AuthenticationError.ERROR
        success = False
        attempts = 0
        result = None
        while not success:
            result = await self._authenticate(chain_user)
            success = not isinstance(result, AuthenticationError)
            attempts += 1
            if success:
                break
            if result == AuthenticationError.INVALID_CREDENTIALS:
                log.error(
                    "Invalid credentials, aborting authentication to avoid lockout"
                )
                break
            if result == AuthenticationError.AUTH_TEMPORARILY_BLOCKED:
                log.error("Authentication temporarily blocked, aborting")
                break
            if attempts >= max_attempts:
                break
            sleep_seconds = 2**attempts
            log.warning(f"Exponential backoff, retrying in {sleep_seconds} seconds...")
            time.sleep(sleep_seconds)
        if not success:
            log.error(
                f"Authentication failed after {attempts} attempt"
                + ("s" if attempts != 1 else "")
            )
        if result is None:
            return AuthenticationError.ERROR
        return result

    @abstractmethod
    async def find_class_by_id(
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
    async def _book_class(
        self,
        auth_data: AuthData,
        class_id: str,
    ) -> BookingResult | BookingError:
        raise NotImplementedError()

    async def try_book_class(
        self,
        chain_identifier: ChainIdentifier,
        auth_data: AuthData,
        _class: RezervoClass,
        config: ConfigValue,
        user_id: UUID,
    ) -> Union[BookingResult, BookingError, AuthenticationError]:
        max_attempts = config.booking.max_attempts
        if max_attempts < 1:
            log.error("Max booking attempts must be a positive number")
            return BookingError.INVALID_CONFIG
        if isinstance(auth_data, AuthenticationError):
            log.error("Invalid authentication")
            return auth_data
        booking_result = None
        attempts = 0
        while attempts < max_attempts:
            booking_result = await self._book_class(auth_data, _class.id)
            attempts += 1
            if isinstance(booking_result, BookingResult):
                break
            if attempts >= BOOKING_INITIAL_BURST_ATTEMPTS:
                sleep_seconds = 2 ** (attempts - BOOKING_INITIAL_BURST_ATTEMPTS)
                log.warning(
                    f"Exponential backoff, retrying in {sleep_seconds} seconds..."
                )
                await asyncio.sleep(sleep_seconds)
        if not isinstance(booking_result, BookingResult):
            log.error(
                f"Booking failed after {attempts} attempt"
                + ("s" if attempts != 1 else "")
            )
            return BookingError.ERROR
        log.info(
            f"Successfully booked class '{_class.activity.name}'"
            + (f" after {attempts} attempts" if attempts != 1 else "")
        )
        aprs.notify(
            notify_type=NotifyType.INFO,
            title=f"Successfully booked '{_class.activity.name}'",
            body=f"Successfully booked '{chain_identifier}' class '{_class.activity.name}'"
            + (f" after {attempts} attempts" if attempts != 1 else ""),
        )
        if config.notifications:
            time_zone_adjusted_class = _class
            time_zone_adjusted_class.start_time = _class.start_time.astimezone(
                pytz.timezone("Europe/Oslo")
            )  # TODO: clean this
            time_zone_adjusted_class.end_time = _class.end_time.astimezone(
                pytz.timezone("Europe/Oslo")
            )  # TODO: clean this
            # ical_url = f"{ICAL_URL}/?id={_class.id}&token={token}"    # TODO: consider re-introducing ical
            await notify_booking(
                config.notifications, chain_identifier, time_zone_adjusted_class
            )
            await notify_class_friends_of_booking(user_id, time_zone_adjusted_class)
        return booking_result

    @abstractmethod
    async def _cancel_booking(
        self,
        auth_data: AuthData,
        _class: RezervoClass,
    ) -> bool:
        raise NotImplementedError()

    async def try_cancel_booking(
        self,
        auth_data: AuthData,
        _class: RezervoClass,
        config: ConfigValue,
        user_id: UUID,
    ) -> Union[None, BookingError, AuthenticationError]:
        if config.booking.max_attempts < 1:
            log.error("Max booking cancellation attempts must be a positive number")
            return BookingError.INVALID_CONFIG
        if isinstance(auth_data, AuthenticationError):
            log.error("Invalid authentication")
            return auth_data
        cancelled = False
        attempts = 0
        while not cancelled:
            cancelled = await self._cancel_booking(auth_data, _class)
            attempts += 1
            if cancelled:
                break
            if attempts >= config.booking.max_attempts:
                break
            if attempts >= BOOKING_INITIAL_BURST_ATTEMPTS:
                sleep_seconds = 2 ** (attempts - BOOKING_INITIAL_BURST_ATTEMPTS)
                log.warning(
                    f"Exponential backoff, retrying in {sleep_seconds} seconds..."
                )
                await asyncio.sleep(sleep_seconds)
        if not cancelled:
            log.error(
                f"Booking cancellation failed after {attempts} attempt"
                + ("s" if attempts != 1 else "")
            )
            return BookingError.ERROR
        log.info(
            f"Successfully cancelled '{_class.activity.name}'"
            + (f" after {attempts} attempts" if attempts != 1 else "")
        )
        await notify_class_friends_of_cancellation(user_id, _class)
        return None

    async def fetch_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> list[UserSession]:
        log.info(
            f":right_arrow_curving_down:  Pulling user sessions from '{chain_user.chain}' for '{chain_user.username}' ..."
        )
        schedule = await self.fetch_schedule(
            datetime.combine(datetime.now(), datetime.min.time()),
            total_days_for_next_whole_weeks(PLANNED_SESSIONS_NEXT_WHOLE_WEEKS),
            locations if locations is not None else self.locations(),
        )
        planned_sessions = self.extract_planned_sessions(chain_user, schedule)
        past_and_booked_sessions = await self._fetch_past_and_booked_sessions(
            chain_user, locations
        )
        if past_and_booked_sessions is None:
            return planned_sessions
        sessions_by_class_id = {s.class_id: s for s in planned_sessions}
        for session in past_and_booked_sessions:
            if session.class_id not in sessions_by_class_id:
                sessions_by_class_id[session.class_id] = session
        return list(sessions_by_class_id.values())

    def extract_planned_sessions(
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
                class_data=SessionRezervoClass(**p.dict()),
            )
            for p in planned_classes
        ]

    @abstractmethod
    async def _fetch_past_and_booked_sessions(
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

    async def check_in_user(
        self,
        chain_identifier: ChainIdentifier,
        chain_user: ChainUser,
        terminal_id: str,
        print_ticket: bool,
    ) -> bool:
        raise NotImplementedError()

    async def fetch_week_schedule(
        self,
        compact_iso_week: str,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        return await self.fetch_schedule(
            from_compact_iso_week(compact_iso_week), 7, locations
        )

    @abstractmethod
    async def verify_authentication(self, credentials: ChainUserCredentials) -> bool:
        raise NotImplementedError()

    async def verify_totp(self, totp: str) -> bool:
        if not self.totp_enabled:
            raise NotImplementedError("TOTP not enabled for this provider")
        if self.totp_regex is None:
            # bypass TOTP verification if no pattern is defined
            return True
        return re.compile(self.totp_regex).match(totp) is not None

    async def initiate_totp_flow(
        self, chain_identifier: ChainIdentifier, user_id: UUID
    ) -> None:
        if not self.totp_enabled:
            raise NotImplementedError("TOTP not enabled for this provider")
        raise NotImplementedError()
