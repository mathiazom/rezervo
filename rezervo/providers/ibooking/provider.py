import asyncio
import math
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Union

import pydantic
import requests
from aiohttp import ClientSession

from rezervo.errors import AuthenticationError, BookingError
from rezervo.providers.ibooking.auth import (
    USER_AGENT,
    IBookingAuthResult,
    authenticate_session,
    authenticate_token,
    fetch_public_token,
)
from rezervo.providers.ibooking.booking import (
    book_ibooking_class,
    cancel_booking,
)
from rezervo.providers.ibooking.schema import (
    IBookingClass,
    IBookingDomain,
    IBookingLocationIdentifier,
    IBookingSchedule,
    IBookingSession,
    session_state_from_ibooking,
    tz_aware_iso_from_ibooking_date_str,
)
from rezervo.providers.ibooking.urls import (
    CLASS_URL,
    CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH,
    CLASSES_SCHEDULE_URL,
    MY_SESSIONS_URL,
)
from rezervo.providers.provider import Provider
from rezervo.providers.schedule import find_class_in_schedule_by_config
from rezervo.providers.schema import LocationIdentifier
from rezervo.schemas.config.user import ChainUser, ChainUserCredentials, Class
from rezervo.schemas.schedule import (
    RezervoActivity,
    RezervoClass,
    RezervoDay,
    RezervoInstructor,
    RezervoLocation,
    RezervoSchedule,
    UserSession,
)
from rezervo.utils.aiohttp_utils import create_tcp_connector
from rezervo.utils.category_utils import determine_activity_category
from rezervo.utils.logging_utils import err


class IBookingProvider(Provider[IBookingAuthResult, IBookingLocationIdentifier]):
    @property
    @abstractmethod
    def ibooking_domain(self) -> IBookingDomain:
        raise NotImplementedError()

    async def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[IBookingAuthResult, AuthenticationError]:
        return await authenticate_token(chain_user)

    async def find_class_by_id(
        self, class_id: str
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        token = await fetch_public_token()
        if isinstance(token, AuthenticationError):
            err.log("Failed to authenticate to iBooking")
            return token
        print(f"Searching for class by id: {class_id}")
        # TODO: handle different domains
        async with ClientSession(connector=create_tcp_connector()) as session:
            async with session.get(
                f"{CLASS_URL}?token={token}&id={class_id}&lang=no"
            ) as class_response:
                if class_response.status != requests.codes.OK:
                    err.log("Class get request failed")
                    return BookingError.ERROR
                ibooking_class = IBookingClass(**(await class_response.json())["class"])
        if ibooking_class is None:
            return BookingError.CLASS_MISSING
        return self.rezervo_class_from_ibooking_class(ibooking_class)

    async def find_class(
        self, _class_config: Class
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        return await self.find_public_ibooking_class(
            self.ibooking_domain,
            _class_config,
        )

    async def _book_class(
        self,
        auth_result: IBookingAuthResult,
        class_id: str,
    ) -> bool:
        # make sure class_id is a valid ibooking class id
        try:
            ibooking_class_id = int(class_id)
        except ValueError:
            err.log(f"Invalid ibooking class id: {class_id}")
            return False
        return await book_ibooking_class(
            self.ibooking_domain, auth_result, ibooking_class_id
        )

    async def _cancel_booking(
        self,
        auth_result: IBookingAuthResult,
        class_id: str,
    ) -> bool:
        # make sure class_id is a valid ibooking class id
        try:
            ibooking_class_id = int(class_id)
        except ValueError:
            err.log(f"Invalid ibooking class id: {class_id}")
            return False
        return await cancel_booking(
            self.ibooking_domain, auth_result, ibooking_class_id
        )

    async def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> Optional[list[UserSession]]:
        async with ClientSession(connector=create_tcp_connector()) as session:
            auth_session = await authenticate_session(
                session, chain_user.username, chain_user.password
            )
            if isinstance(auth_session, AuthenticationError):
                err.log(f"Authentication failed for '{chain_user.username}'!")
                return None
            try:
                async with auth_session.get(
                    MY_SESSIONS_URL, headers={"User-Agent": USER_AGENT}
                ) as res:
                    sessions_json = await res.json()
            except requests.exceptions.RequestException as e:
                err.log(
                    f"Failed to retrieve sessions for '{chain_user.username}'",
                    e,
                )
                return None
        ibooking_sessions = []
        for s in sessions_json:
            if s["type"] != "groupclass":
                continue
            ibooking_sessions.append(pydantic.parse_obj_as(IBookingSession, s))
        past_and_booked_sessions = [
            UserSession(
                chain=chain_user.chain,
                class_id=s.class_field.id,
                user_id=chain_user.user_id,
                status=session_state_from_ibooking(s.status),
                class_data=self.rezervo_class_from_ibooking_class(s.class_field),
            )
            for s in ibooking_sessions
        ]
        return past_and_booked_sessions

    async def fetch_schedule(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        return await self.fetch_ibooking_schedule(
            self.ibooking_domain,
            await fetch_public_token(),
            days,
            studios=(
                [
                    s
                    for location in locations
                    if (
                        s := self.provider_location_identifier_from_location_identifier(
                            location
                        )
                    )
                    is not None
                ]
            ),
            from_date=from_date,
        )

    def rezervo_class_from_ibooking_class(
        self, ibooking_class: IBookingClass
    ) -> RezervoClass:
        return RezervoClass(
            id=ibooking_class.id,
            start_time=tz_aware_iso_from_ibooking_date_str(ibooking_class.from_field),
            end_time=tz_aware_iso_from_ibooking_date_str(ibooking_class.to),
            location=RezervoLocation(
                id=self.location_from_provider_location_identifier(
                    ibooking_class.studio.id
                ),
                studio=ibooking_class.studio.name,
                room=ibooking_class.room,
            ),
            is_bookable=ibooking_class.bookable,
            is_cancelled=ibooking_class.cancelText is not None,
            total_slots=ibooking_class.capacity,
            available_slots=ibooking_class.available,
            waiting_list_count=ibooking_class.waitlist.count,
            activity=RezervoActivity(
                id=str(ibooking_class.activityId),
                name=ibooking_class.name,
                category=determine_activity_category(ibooking_class.category.name).name,
                description=ibooking_class.description,
                color=ibooking_class.color,
                image=ibooking_class.image,
            ),
            instructors=[
                RezervoInstructor(name=s.name) for s in ibooking_class.instructors
            ],
            user_status=ibooking_class.userStatus,
            booking_opens_at=tz_aware_iso_from_ibooking_date_str(
                ibooking_class.bookingOpensAt
            ),
        )

    async def fetch_single_batch_ibooking_schedule(
        self,
        domain: IBookingDomain,
        token: str,
        studios: Optional[list[int]] = None,
        from_iso: Optional[str] = None,
    ) -> Union[RezervoSchedule, None]:
        # TODO: support different domains (not just sit.no)
        if domain != "sit":
            raise NotImplementedError()
        async with ClientSession(connector=create_tcp_connector()) as session:
            async with session.get(
                f"{CLASSES_SCHEDULE_URL}"
                f"?token={token}"
                f"{f'&from={from_iso}' if from_iso is not None else ''}"
                f"{('&studios=' + ','.join([str(s) for s in studios])) if studios else ''}"
                f"&lang=no"
            ) as res:
                if res.status != requests.codes.OK:
                    return None
                json_res = await res.json()
        return RezervoSchedule(
            days=[
                RezervoDay(
                    date=day.date,
                    day_name=day.dayName,
                    classes=[
                        self.rezervo_class_from_ibooking_class(c) for c in day.classes
                    ],
                )
                for day in IBookingSchedule(**json_res).days
            ]
        )

    async def fetch_ibooking_schedule(
        self,
        domain: IBookingDomain,
        token,
        days: int,
        from_date: datetime = datetime.combine(datetime.now(), datetime.min.time()),
        studios: Optional[list[int]] = None,
    ) -> RezervoSchedule:
        schedule_tasks = []
        for _i in range(math.ceil(days / CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH)):
            schedule_tasks.append(
                self.fetch_single_batch_ibooking_schedule(
                    domain,
                    token,
                    studios,
                    from_date.isoformat(),
                )
            )
            from_date = from_date + timedelta(
                days=CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH
            )
        schedule_days: list[RezervoDay] = []
        for batch in await asyncio.gather(*schedule_tasks):
            if batch is None:
                continue
            # api actually returns 7 days, but the extra days are empty...
            schedule_days.extend(batch.days[:CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH])
        return RezervoSchedule(days=schedule_days[:days])

    # Search the scheduled classes and return the first class matching the given arguments
    async def find_public_ibooking_class(
        self,
        domain: IBookingDomain,
        _class_config: Class,
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        token = await fetch_public_token()
        if isinstance(token, AuthenticationError):
            err.log("Failed to fetch public token")
            return token
        schedule = await self.fetch_ibooking_schedule(
            domain,
            token,
            14,
            studios=[studio]
            if (
                studio := self.provider_location_identifier_from_location_identifier(
                    _class_config.location_id
                )
            )
            is not None
            else None,
        )
        if schedule is None:
            err.log("Schedule get request denied")
            return BookingError.ERROR
        return find_class_in_schedule_by_config(_class_config, schedule)

    async def verify_authentication(self, credentials: ChainUserCredentials) -> bool:
        async with ClientSession() as session:
            return not isinstance(
                await authenticate_session(
                    session, credentials.username, credentials.password
                ),
                AuthenticationError,
            )
