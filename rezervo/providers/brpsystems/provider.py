import asyncio
import datetime
import re
from abc import abstractmethod
from typing import Optional, Union

import pydantic
import requests
from apprise import NotifyType
from pydantic.tools import parse_obj_as

from rezervo.consts import WEEKDAYS
from rezervo.errors import AuthenticationError, BookingError
from rezervo.http_client import HttpClient
from rezervo.notify.apprise import aprs
from rezervo.providers.brpsystems.auth import authenticate
from rezervo.providers.brpsystems.booking import (
    MAX_SCHEDULE_SEARCH_ATTEMPTS,
    SCHEDULE_SEARCH_ATTEMPT_DAYS,
    book_brp_class,
    booking_url,
    cancel_brp_booking,
)
from rezervo.providers.brpsystems.schedule import (
    fetch_brp_class,
    fetch_brp_schedule,
    fetch_detailed_brp_class,
    fetch_detailed_brp_schedule,
)
from rezervo.providers.brpsystems.schema import (
    BookingData,
    BookingType,
    BrpAuthData,
    BrpClass,
    BrpLocationIdentifier,
    BrpSubdomain,
    DetailedBrpClass,
    session_state_from_brp,
    tz_aware_iso_from_brp_date_str,
)
from rezervo.providers.provider import Provider
from rezervo.providers.schedule import find_class_in_schedule_by_config
from rezervo.providers.schema import LocationIdentifier
from rezervo.schemas.config.user import (
    ChainIdentifier,
    ChainUser,
    ChainUserCredentials,
    Class,
)
from rezervo.schemas.schedule import (
    BookingResult,
    RezervoActivity,
    RezervoClass,
    RezervoDay,
    RezervoInstructor,
    RezervoLocation,
    RezervoSchedule,
    SessionRezervoClass,
    UserSession,
)
from rezervo.utils.apprise_utils import aprs_ctx
from rezervo.utils.category_utils import determine_activity_category
from rezervo.utils.logging_utils import log


class BrpProvider(Provider[BrpAuthData, BrpLocationIdentifier]):
    @property
    @abstractmethod
    def brp_subdomain(self) -> BrpSubdomain:
        raise NotImplementedError()

    async def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[BrpAuthData, AuthenticationError]:
        if chain_user.password is None:
            return AuthenticationError.INVALID_CREDENTIALS
        return await authenticate(
            self.brp_subdomain, chain_user.username, chain_user.password
        )

    async def find_class_by_id(
        self, class_id: str
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        locations = self.locations()
        business_unit = (
            self.provider_location_identifier_from_location_identifier(locations[0])
            if len(locations) > 0
            else None
        )
        if business_unit is None:
            return BookingError(
                "Must be aware of at least one location to search for a class by id"
            )
        # `business_unit` can be any valid business unit, does not need to be the one actually hosting the class...
        brp_class = await fetch_brp_class(
            self.brp_subdomain,
            business_unit,
            class_id,
        )
        if brp_class is None:
            return BookingError.CLASS_MISSING
        detailed_brp_class = await fetch_detailed_brp_class(
            self.brp_subdomain, brp_class
        )
        return self.rezervo_class_from_brp_class(
            self.brp_subdomain,
            detailed_brp_class if detailed_brp_class is not None else brp_class,
        )

    async def find_class(
        self, _class_config: Class
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        _class = await self.try_find_brp_class(
            self.brp_subdomain,
            _class_config,
        )
        if isinstance(_class, RezervoClass):
            return _class
        return BookingError.CLASS_MISSING

    async def _book_class(
        self,
        auth_data: BrpAuthData,
        class_id: str,
    ) -> BookingResult | BookingError:
        # make sure class_id is a valid brp class id
        try:
            brp_class_id = int(class_id)
        except ValueError:
            log.error(f"Invalid brp class id: {class_id}")
            return BookingError.MALFORMED_CLASS
        return await book_brp_class(self.brp_subdomain, auth_data, brp_class_id)

    async def _cancel_booking(
        self,
        auth_data: BrpAuthData,
        _class: RezervoClass,
    ) -> bool:
        # make sure class_id is a valid brp class id
        try:
            brp_class_id = int(_class.id)
        except ValueError:
            log.error(f"Invalid brp class id: {_class.id}")
            return False
        # TODO: consider memoizing retrieval of booking reference and type
        try:
            async with HttpClient.singleton().get(
                booking_url(self.brp_subdomain, auth_data, datetime.datetime.now()),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {auth_data.access_token}",
                },
            ) as res:
                bookings_response = parse_obj_as(list[BookingData], await res.json())
        except requests.exceptions.RequestException as e:
            log.error(
                f"Failed to retrieve booked classes for cancellation of class '{_class.activity.name}' (id={brp_class_id})",
                e,
            )
            return False
        if bookings_response is None:
            return False
        booking_id = None
        booking_type: Optional[BookingType] = None
        for booking in bookings_response:
            if booking.groupActivity.id == brp_class_id:
                booking_type = booking.type
                booking_id = booking.dict()[str(booking.type.value)]["id"]
                break
        if booking_id is None or booking_type is None:
            log.error(
                f"No sessions active matching the cancellation criteria for class '{_class.activity.name}' (id={brp_class_id})",
            )
            return False
        return await cancel_brp_booking(
            self.brp_subdomain, auth_data, booking_id, booking_type
        )

    async def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> Optional[list[UserSession]]:
        start_time = datetime.datetime.combine(
            datetime.datetime.now(), datetime.datetime.min.time()
        ) - datetime.timedelta(weeks=3)
        auth_data = await self._authenticate(chain_user)
        if isinstance(auth_data, AuthenticationError):
            log.error(
                f"Authentication failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return None
        try:
            async with HttpClient.singleton().get(
                booking_url(
                    self.brp_subdomain,
                    auth_data,
                    start_time_point=start_time,
                ),
                headers={
                    "Authorization": f"Bearer {auth_data.access_token}",
                },
            ) as res:
                bookings_response: list[BookingData] = await res.json()
        except requests.exceptions.RequestException as e:
            log.error(
                f"Failed to retrieve sessions for '{chain_user.username}'",
                e,
            )
            with aprs_ctx() as error_ctx:
                aprs.notify(
                    notify_type=NotifyType.FAILURE,
                    title=f"Failed to retrieve '{chain_user.chain}' sessions",
                    body=f"Failed to retrieve '{chain_user.chain}' sessions for '{chain_user.username}'",
                    attach=[error_ctx],
                )
            return None
        brp_sessions = []
        for s in bookings_response:
            brp_sessions.append(pydantic.parse_obj_as(BookingData, s))
        past_and_imminent_sessions = []
        for s in brp_sessions:
            # TODO: fetch concurrently
            _class = await self.find_class_by_id(str(s.groupActivity.id))
            if not isinstance(_class, RezervoClass):
                continue
            past_and_imminent_sessions.append(
                UserSession(
                    chain=chain_user.chain,
                    class_id=str(s.groupActivity.id),
                    user_id=chain_user.user_id,
                    status=session_state_from_brp(
                        s.type, _class.start_time, s.checkedIn
                    ),
                    position_in_wait_list=(
                        s.waitingListBooking.waitingListPosition
                        if s.waitingListBooking is not None
                        else None
                    ),
                    class_data=SessionRezervoClass(**_class.dict()),
                )
            )
        return past_and_imminent_sessions

    async def _fetch_detailed_schedule(
        self, business_unit: int, days: int, from_date: datetime.datetime
    ) -> list[DetailedBrpClass]:
        schedule = await fetch_brp_schedule(
            self.brp_subdomain,
            business_unit,
            days,
            from_date=from_date,
        )
        return await fetch_detailed_brp_schedule(self.brp_subdomain, schedule)

    def _rezervo_schedule_from_brp_schedule(
        self,
        from_date: datetime.datetime,
        days: int,
        schedule: list[BrpClass] | list[DetailedBrpClass],
    ) -> RezervoSchedule:
        days_map: dict[datetime.date, list[RezervoClass]] = {
            from_date.date() + datetime.timedelta(days=i): [] for i in range(days)
        }
        for _class in schedule:
            class_date = datetime.datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(_class.duration.start)
            ).date()
            days_map[class_date].append(
                self.rezervo_class_from_brp_class(
                    self.brp_subdomain,
                    _class,
                )
            )
        return RezervoSchedule(
            days=[
                RezervoDay(
                    day_name=WEEKDAYS[date.weekday()],
                    date=date.isoformat(),
                    classes=sorted(
                        day_classes,
                        key=lambda c: c.start_time,
                    ),
                )
                for date, day_classes in days_map.items()
            ]
        )

    async def fetch_schedule(
        self,
        from_date: datetime.datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        schedule: list[DetailedBrpClass] = []
        for res in await asyncio.gather(
            *[
                self._fetch_detailed_schedule(business_unit, days, from_date)
                for location in locations
                if (
                    business_unit := self.provider_location_identifier_from_location_identifier(
                        location
                    )
                )
                is not None
            ]
        ):
            schedule.extend(res)
        return self._rezervo_schedule_from_brp_schedule(from_date, days, schedule)

    def rezervo_class_from_brp_class(
        self,
        subdomain: BrpSubdomain,
        brp_class: BrpClass | DetailedBrpClass,
    ) -> RezervoClass:
        category = determine_activity_category(brp_class.name)
        return RezervoClass(
            id=str(brp_class.id),  # TODO: check if unique across all subdomains
            start_time=datetime.datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(brp_class.duration.start)
            ),
            end_time=datetime.datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(brp_class.duration.end)
            ),
            location=RezervoLocation(
                id=self.location_from_provider_location_identifier(  # type: ignore
                    brp_class.businessUnit.id
                ),
                studio=brp_class.businessUnit.name,
                room=", ".join([location.name for location in brp_class.locations]),
            ),
            is_bookable=datetime.datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(brp_class.bookableEarliest)
            )
            < datetime.datetime.now().astimezone()
            < datetime.datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(brp_class.bookableLatest)
            ),
            is_cancelled=brp_class.cancelled,
            total_slots=brp_class.slots.total,
            available_slots=brp_class.slots.leftToBook,
            waiting_list_count=brp_class.slots.inWaitingList,
            activity=RezervoActivity(
                id=str(brp_class.groupActivityProduct.id),
                name=re.sub(r"\s\(\d+\)$", "", brp_class.groupActivityProduct.name),
                category=category.name,
                description=(
                    brp_class.activity_details.description
                    if isinstance(brp_class, DetailedBrpClass)
                    else ""
                ),
                additional_information=brp_class.externalMessage,
                color=category.color,
                image=(
                    brp_class.activity_details.image_url
                    if isinstance(brp_class, DetailedBrpClass)
                    else None
                ),
            ),
            instructors=[RezervoInstructor(name=s.name) for s in brp_class.instructors],
            user_status=None,
            booking_opens_at=datetime.datetime.fromisoformat(
                tz_aware_iso_from_brp_date_str(brp_class.bookableEarliest)
            ),
        )

    # TODO: generalize
    async def try_find_brp_class(
        self,
        subdomain: BrpSubdomain,
        _class_config: Class,
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        business_unit = self.provider_location_identifier_from_location_identifier(
            _class_config.location_id
        )
        if business_unit is None:
            log.error(
                f"Could not find business unit matching location id {_class_config.location_id}"
            )
            return BookingError.ERROR
        attempts = 0
        brp_class = None
        now_date = datetime.datetime.now()
        from_date = datetime.datetime(now_date.year, now_date.month, now_date.day)
        search_result = None
        days_per_search = SCHEDULE_SEARCH_ATTEMPT_DAYS
        while attempts < MAX_SCHEDULE_SEARCH_ATTEMPTS:
            brp_schedule = await fetch_brp_schedule(
                subdomain,
                business_unit,
                days=days_per_search,
                from_date=from_date,
            )
            if brp_schedule is None:
                log.error("Schedule get request denied")
                return BookingError.ERROR
            search_result = find_class_in_schedule_by_config(
                _class_config,
                self._rezervo_schedule_from_brp_schedule(
                    from_date, days_per_search, brp_schedule
                ),
            )
            if (
                search_result is not None
                and not isinstance(search_result, BookingError)
                and not isinstance(search_result, AuthenticationError)
            ):
                if brp_class is None:
                    brp_class = search_result
                else:
                    # Check if class has closer booking date than any already found class
                    now = datetime.datetime.now().astimezone()
                    new_booking_delta = abs(now - search_result.booking_opens_at)
                    existing_booking_delta = abs(now - brp_class.booking_opens_at)
                    if new_booking_delta < existing_booking_delta:
                        brp_class = search_result
                    else:
                        break
            from_date += datetime.timedelta(days=days_per_search)
            attempts += 1
        if brp_class is None:
            log.warning(f"Could not find class matching criteria: {_class_config}")
            if search_result is None:
                return BookingError.CLASS_MISSING
            return search_result
        return brp_class

    async def verify_authentication(self, credentials: ChainUserCredentials) -> bool:
        return credentials.password is not None and not isinstance(
            await authenticate(
                self.brp_subdomain, credentials.username, credentials.password
            ),
            AuthenticationError,
        )

    async def check_in_user(
        self,
        chain_identifier: ChainIdentifier,
        chain_user: ChainUser,
        terminal_id: str,
        print_ticket: bool,
    ) -> bool:
        auth_data = await self._authenticate(chain_user)
        if isinstance(auth_data, AuthenticationError):
            log.error(
                f"Authentication failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return False
        async with HttpClient.singleton().post(
            f"https://{chain_identifier}.brpsystems.com/brponline/api/ver3/customers/{auth_data.username}/passagetries",
            json={
                "cardReader": int(terminal_id),
                "printTicket": print_ticket,
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_data.access_token}",
            },
        ) as res:
            if res.status != requests.codes.CREATED:
                log.error("Check in failed: " + (await res.text()))
                return False
        return True
