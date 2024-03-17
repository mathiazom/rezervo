import asyncio
import re
from abc import ABC
from datetime import datetime, timedelta
from typing import Optional, Union

from aiohttp import FormData

from rezervo.consts import WEEKDAYS
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.models import SessionState
from rezervo.providers.provider import Provider
from rezervo.providers.sats.auth import (
    SatsAuthResult,
    create_sats_session,
    fetch_authed_sats_cookie,
    validate_token,
)
from rezervo.providers.sats.consts import SATS_EXPOSED_CLASSES_DAYS_INTO_FUTURE
from rezervo.providers.sats.helpers import create_activity_id, retrieve_sats_page_props
from rezervo.providers.sats.schedule import (
    fetch_sats_classes,
)
from rezervo.providers.sats.schema import (
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
from rezervo.utils.logging_utils import err, warn


class SatsProvider(Provider[SatsAuthResult, SatsLocationIdentifier], ABC):
    async def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[SatsAuthResult, AuthenticationError]:
        if chain_user.auth_token is not None:
            if await validate_token(chain_user.auth_token) is None:
                return chain_user.auth_token
            warn.log(
                "Authentication token validation failed, retrieving fresh token..."
            )
        token_res = await fetch_authed_sats_cookie(
            chain_user.username, chain_user.password
        )
        if isinstance(token_res, AuthenticationError):
            err.log("Failed to extract authentication token!")
            return token_res
        validation_error = await validate_token(token_res)
        if validation_error is not None:
            return validation_error
        with SessionLocal() as db:
            crud.upsert_chain_user_token(
                db, chain_user.user_id, chain_user.chain, token_res
            )
        return token_res

    async def find_class_by_id(
        self, class_id: str
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        schedule = await self.fetch_schedule(
            datetime.now(), 14, [self.extract_location_id(class_id)]
        )
        for day in schedule.days:
            for _class in day.classes:
                if _class.id == class_id:
                    return _class
        return BookingError.CLASS_MISSING

    async def find_class(
        self, _class_config: Class
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        schedule = await self.fetch_schedule(
            datetime.now(), 14, [_class_config.location_id]
        )
        for day in schedule.days:
            for _class in day.classes:
                if (
                    _class.activity.id == _class_config.activity_id
                    and _class.start_time.weekday() == _class_config.weekday
                    and _class.location.id == _class_config.location_id
                    and _class.start_time.hour == _class_config.start_time.hour
                    and _class.start_time.minute == _class_config.start_time.minute
                ):
                    return _class
        return BookingError.CLASS_MISSING

    async def _book_class(
        self,
        auth_result: SatsAuthResult,
        class_id: str,
    ) -> bool:
        async with create_sats_session(auth_result) as session:
            async with session.post(
                BOOKING_URL, headers={"Accept": "text/html"}, data={"id": class_id}
            ) as res:
                if not res.ok:
                    err.log("Booking attempt failed: " + (await res.text()))
                    return False
                return True

    async def _cancel_booking(
        self,
        auth_result: SatsAuthResult,
        class_id: str,
    ) -> bool:
        _class = await self.find_class_by_id(class_id)
        if not isinstance(_class, RezervoClass):
            return False
        async with create_sats_session(auth_result) as session:
            async with session.get(
                BOOKINGS_URL, headers={"Accept": "text/html"}
            ) as bookings_res:
                sats_day_bookings = SatsBookingsResponse(
                    **retrieve_sats_page_props(str(await bookings_res.read()))
                ).myUpcomingTraining
            for day_bookings in sats_day_bookings:
                for booking in day_bookings.upcomingTrainings.trainings:
                    start_time = datetime.strptime(
                        booking.date + " " + booking.startTime, "%Y-%m-%d %H:%M"
                    ).astimezone()
                    if (
                        booking.activityName == _class.activity.name
                        and booking.instructor == _class.instructors[0].name
                        and start_time == _class.start_time
                    ):
                        async with session.post(
                            CANCEL_BOOKING_URL,
                            headers={"Accept": "text/html"},
                            data=FormData(
                                {
                                    "participationId": booking.hiddenInput[0].value,
                                    "redirectUrl": BOOKINGS_PATH,
                                }
                            ),
                        ) as res:
                            return res.ok
        return False

    async def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> Optional[list[UserSession]]:
        auth_result = await self._authenticate(chain_user)
        if isinstance(auth_result, AuthenticationError):
            err.log(f"Authentication failed for '{chain_user.username}'!")
            return None
        async with create_sats_session(auth_result) as session:
            async with session.get(
                BOOKINGS_URL, headers={"Accept": "text/html"}
            ) as bookings_res:
                sats_day_bookings = SatsBookingsResponse(
                    **retrieve_sats_page_props(str(await bookings_res.read()))
                ).myUpcomingTraining

        user_sessions = []
        for day_booking in sats_day_bookings:
            for training in day_booking.upcomingTrainings.trainings:
                start_time = datetime.strptime(
                    training.date + " " + training.startTime, "%Y-%m-%d %H:%M"
                )
                _class = await self.find_class(
                    Class(
                        activity_id=create_activity_id(training.activityName),
                        weekday=start_time.weekday(),
                        location_id=self.extract_location_id(
                            training.hiddenInput[0].value
                        ),
                        start_time=ClassTime(
                            hour=start_time.hour, minute=start_time.minute
                        ),
                    )
                )
                if not isinstance(_class, RezervoClass):
                    continue

                user_session = UserSession(
                    chain=chain_user.chain,
                    class_id=_class.id,
                    user_id=chain_user.user_id,
                    status=(
                        SessionState.WAITLIST
                        if training.waitingListIndex > 0
                        else SessionState.BOOKED
                    ),
                    class_data=SessionRezervoClass(**_class.__dict__),
                )
                user_sessions.append(user_session)

        return user_sessions

    async def fetch_schedule(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        club_ids = [
            str(self.provider_location_identifier_from_location_identifier(loc) or "")
            for loc in locations
        ]

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
        classes_are_fetchable = (
            datetime.now().date()
            <= date.date()
            < (
                datetime.now() + timedelta(days=SATS_EXPOSED_CLASSES_DAYS_INTO_FUTURE)
            ).date()
        )
        sats_classes = (
            await fetch_sats_classes(club_ids, date) if classes_are_fetchable else []
        )
        return RezervoDay(
            day_name=WEEKDAYS[date.weekday()],
            date=date.isoformat(),
            classes=[
                self.rezervo_class_from_sats_class(sats_class)
                for sats_class in sats_classes
            ],
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
                    sats_class.metadata.name,
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
