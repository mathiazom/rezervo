import asyncio
import re
from abc import ABC
from datetime import datetime, timedelta
from typing import Callable, Optional, Union

import pytz
from aiohttp import FormData

from rezervo.consts import WEEKDAYS
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.models import SessionState
from rezervo.providers.provider import Provider
from rezervo.providers.sats.auth import (
    SatsAuthData,
    create_authed_sats_session,
    fetch_authed_sats_cookie,
    validate_token,
)
from rezervo.providers.sats.consts import (
    SATS_EXPOSED_CLASSES_DAYS_INTO_FUTURE,
)
from rezervo.providers.sats.helpers import (
    club_name_from_center_name,
    create_activity_id,
    retrieve_sats_page_props,
)
from rezervo.providers.sats.schedule import (
    fetch_sats_classes,
    find_sats_class,
    is_schedule_fetchable_for_date,
)
from rezervo.providers.sats.schema import (
    SatsBooking,
    SatsBookingsResponse,
    SatsClass,
    SatsLocationIdentifier,
)
from rezervo.providers.sats.urls import (
    BOOKING_URL,
    BOOKINGS_PATH,
    BOOKINGS_URL,
    CANCEL_BOOKING_URL,
)
from rezervo.providers.schema import LocationIdentifier
from rezervo.schemas.config.user import (
    ChainUser,
    ChainUserCredentials,
    Class,
    ClassTime,
)
from rezervo.schemas.schedule import (
    RezervoActivity,
    RezervoClass,
    RezervoDay,
    RezervoInstructor,
    RezervoLocation,
    RezervoSchedule,
    SessionRezervoClass,
    UserSession,
)
from rezervo.utils.category_utils import determine_activity_category
from rezervo.utils.logging_utils import log


class SatsProvider(Provider[SatsAuthData, SatsLocationIdentifier], ABC):
    async def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[SatsAuthData, AuthenticationError]:
        if chain_user.auth_data is not None:
            if await validate_token(chain_user.auth_data) is None:
                return chain_user.auth_data
            log.warning(
                f"Validation of Sats authentication token failed for '{chain_user.username}', retrieving fresh token..."
            )
        auth_data = await fetch_authed_sats_cookie(
            chain_user.username, chain_user.password
        )
        if isinstance(auth_data, AuthenticationError):
            log.error(
                f"Failed to authenticate '{chain_user.chain}' user '{chain_user.username}'"
            )
            return auth_data
        validation_error = await validate_token(auth_data)
        if validation_error is not None:
            return validation_error
        with SessionLocal() as db:
            crud.upsert_chain_user_auth_data(
                db, chain_user.chain, chain_user.user_id, auth_data
            )
        return auth_data

    async def _search_for_class(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
        comparator_fn: Callable[[SatsClass], bool],
    ):
        club_ids = self.club_ids_from_locations(locations)
        tasks = []
        for i in range(days):
            fetch_date = from_date + timedelta(days=i)
            if is_schedule_fetchable_for_date(fetch_date.date()):
                tasks.append(
                    asyncio.create_task(
                        find_sats_class(
                            club_ids,
                            fetch_date,
                            comparator_fn,
                        )
                    )
                )
        for coro in asyncio.as_completed(tasks):
            try:
                res = await coro
            except asyncio.CancelledError:
                for t in tasks:
                    t.cancel()
                raise
            if res is not None:
                for t in tasks:
                    t.cancel()
                return self.rezervo_class_from_sats_class(res)
        return BookingError.CLASS_MISSING

    async def find_class_by_id(
        self, class_id: str
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        def comparator_fn(sats_class: SatsClass):
            return class_id == sats_class.id

        return await self._search_for_class(
            datetime.now(),
            SATS_EXPOSED_CLASSES_DAYS_INTO_FUTURE,
            [self.extract_location_id(class_id)],
            comparator_fn,
        )

    async def find_class(
        self, _class_config: Class
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        def comparator_fn(sats_class: SatsClass):
            _class = self.rezervo_class_from_sats_class(sats_class)
            return (
                _class.activity.id == _class_config.activity_id
                and _class.start_time.weekday() == _class_config.weekday
                and _class.location.id == _class_config.location_id
                and _class.start_time.hour == _class_config.start_time.hour
                and _class.start_time.minute == _class_config.start_time.minute
            )

        # TODO: booking opening time is, in a non-obvious way, assumed to be 7 days before the class starts
        #       booking rules should possibly be hardcoded instead to determine class with closest booking time
        return await self._search_for_class(
            _class_config.calculate_next_occurrence(include_today=False),
            1,
            [_class_config.location_id],
            comparator_fn,
        )

    async def _book_class(
        self,
        auth_data: SatsAuthData,
        class_id: str,
    ) -> bool:
        async with create_authed_sats_session(auth_data) as session:
            async with session.post(BOOKING_URL, data={"id": class_id}) as res:
                if not res.ok:
                    log.error("Booking attempt failed: " + (await res.text()))
                    return False
                return True

    async def _cancel_booking(
        self,
        auth_data: SatsAuthData,
        _class: RezervoClass,
    ) -> bool:
        async with create_authed_sats_session(auth_data) as session:
            async with session.get(BOOKINGS_URL) as bookings_res:
                sats_day_bookings = SatsBookingsResponse(
                    **retrieve_sats_page_props(str(await bookings_res.read()))
                ).myUpcomingTraining
            for day_bookings in sats_day_bookings:
                for booking in day_bookings.upcomingTrainings.trainings:
                    start_time = pytz.timezone("Europe/Oslo").localize(
                        datetime.fromisoformat(f"{booking.date}T{booking.startTime}")
                    )
                    if (
                        club_name_from_center_name(booking.centerName)
                        == _class.location.studio
                        and booking.activityName == _class.activity.name
                        and booking.instructor == _class.instructors[0].name
                        and start_time == _class.start_time
                    ):
                        async with session.post(
                            CANCEL_BOOKING_URL,
                            data=FormData(
                                {
                                    "participationId": booking.hiddenInput[0].value,
                                    "redirectUrl": BOOKINGS_PATH,
                                }
                            ),
                        ) as res:
                            return res.ok
        return False

    async def _find_class_from_booking_task(
        self, booking: SatsBooking, class_config: Class
    ) -> tuple[SatsBooking, Union[RezervoClass, BookingError, AuthenticationError]]:
        return booking, await self.find_class(class_config)

    async def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> Optional[list[UserSession]]:
        auth_data = await self._authenticate(chain_user)
        if isinstance(auth_data, AuthenticationError):
            log.error(
                f"Authentication failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return None
        async with create_authed_sats_session(auth_data) as session:
            async with session.get(BOOKINGS_URL) as bookings_res:
                sats_day_bookings = SatsBookingsResponse(
                    **retrieve_sats_page_props(str(await bookings_res.read()))
                ).myUpcomingTraining
        find_class_tasks = []
        for day_booking in sats_day_bookings:
            for booking in day_booking.upcomingTrainings.trainings:
                start_time = pytz.timezone("Europe/Oslo").localize(
                    datetime.fromisoformat(f"{booking.date}T{booking.startTime}")
                )
                find_class_tasks.append(
                    self._find_class_from_booking_task(
                        booking,
                        Class(
                            activity_id=create_activity_id(
                                booking.activityName,
                                club_name_from_center_name(booking.centerName),
                            ),
                            weekday=start_time.weekday(),
                            location_id=self.extract_location_id(
                                booking.hiddenInput[0].value
                            ),
                            start_time=ClassTime(
                                hour=start_time.hour, minute=start_time.minute
                            ),
                        ),
                    )
                )
        user_sessions = []
        for booking, _class in await asyncio.gather(*find_class_tasks):
            if isinstance(_class, RezervoClass):
                user_sessions.append(
                    UserSession(
                        chain=chain_user.chain,
                        class_id=_class.id,
                        user_id=chain_user.user_id,
                        status=(
                            SessionState.WAITLIST
                            if booking.waitingListIndex > 0
                            else SessionState.BOOKED
                        ),
                        position_in_wait_list=(
                            booking.waitingListIndex
                            if booking.waitingListIndex > 0
                            else None
                        ),
                        class_data=SessionRezervoClass(**_class.dict()),
                    )
                )
        return user_sessions

    def club_ids_from_locations(self, locations: list[str]) -> list[str]:
        return [
            str(c)
            for loc in locations
            if (c := self.provider_location_identifier_from_location_identifier(loc))
            is not None
        ]

    async def fetch_schedule(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        club_ids = self.club_ids_from_locations(locations)
        return RezervoSchedule(
            days=await asyncio.gather(
                *(
                    self.fetch_sats_classes_as_rezervo_day(
                        from_date + timedelta(days=i), club_ids
                    )
                    for i in range(days)
                )
            )
        )

    async def fetch_sats_classes_as_rezervo_day(
        self, date: datetime, club_ids: list[str]
    ) -> RezervoDay:
        return RezervoDay(
            day_name=WEEKDAYS[date.weekday()],
            date=date.isoformat(),
            classes=(
                [
                    self.rezervo_class_from_sats_class(sats_class)
                    for sats_class in await fetch_sats_classes(club_ids, date)
                ]
                if is_schedule_fetchable_for_date(date.date())
                else []
            ),
        )

    def rezervo_class_from_sats_class(
        self,
        sats_class: SatsClass,
    ) -> RezervoClass:
        category = determine_activity_category(sats_class.metadata.name)
        start_time = datetime.fromisoformat(sats_class.metadata.startsAt)
        return RezervoClass(
            id=sats_class.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=sats_class.metadata.duration),
            location=RezervoLocation(
                id=self.extract_location_id(sats_class.id),
                studio=sats_class.metadata.clubName,
            ),
            is_bookable=start_time
            - timedelta(days=7)  # https://www.sats.no/legal/bookingregler
            < datetime.now().astimezone()
            < start_time - timedelta(minutes=10),
            is_cancelled=False,  # Sats seemingly does not expose a class is canceled
            total_slots=None,
            available_slots=None,
            waiting_list_count=sats_class.waitingListCount,
            activity=RezervoActivity(
                id=create_activity_id(
                    sats_class.metadata.name, sats_class.metadata.clubName
                ),  # Sats does not provide activity ids
                name=sats_class.metadata.name,
                category=category.name,
                description=sats_class.text,
                color=category.color,
                image=None if sats_class.image is None else sats_class.image.src,
            ),
            instructors=[
                RezervoInstructor(
                    name=sats_class.metadata.instructor.replace("m/ ", "")
                )
            ],
            user_status=None,
            booking_opens_at=start_time - timedelta(days=7),
        )

    def extract_location_id(self, sats_id: str) -> str:
        provider_location_id_match = re.search(r"(\d+)p", sats_id)
        if not provider_location_id_match:
            raise Exception("Could not retrieve location id from sats_id")
        provider_location_id = int(provider_location_id_match.group(1))
        location_id = self.location_from_provider_location_identifier(
            provider_location_id
        )
        if location_id is None:
            raise Exception(
                f"Failed to find location_id for provider_location_id: {provider_location_id}"
            )
        return location_id

    async def verify_authentication(self, credentials: ChainUserCredentials) -> bool:
        return not isinstance(
            await fetch_authed_sats_cookie(credentials.username, credentials.password),
            AuthenticationError,
        )
