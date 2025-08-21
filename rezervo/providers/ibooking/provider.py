import asyncio
import math
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Union
from uuid import UUID

import pydantic

from rezervo.errors import AuthenticationError, BookingError
from rezervo.http_client import HttpClient, create_client_session
from rezervo.models import SessionState
from rezervo.providers.ibooking.auth import (
    IBookingAuthData,
    extend_auth_session_silently,
    fetch_public_ibooking_token,
    initiate_auth_session_interactively,
    refresh_chain_user_auth_data,
    verify_sit_credentials,
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
    SitSession,
    ibooking_class_from_sit_session_class,
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
from rezervo.utils.category_utils import determine_activity_category
from rezervo.utils.logging_utils import log
from rezervo.utils.str_utils import standardize_activity_name


class IBookingProvider(Provider[IBookingAuthData, IBookingLocationIdentifier]):

    @property
    def totp_enabled(self) -> bool:
        return True

    @property
    def totp_regex(self) -> Optional[str]:
        return "^\\d{6}$"

    @property
    @abstractmethod
    def ibooking_domain(self) -> IBookingDomain:
        raise NotImplementedError()

    async def _authenticate(
        self, chain_user: ChainUser
    ) -> Union[IBookingAuthData, AuthenticationError]:
        return await refresh_chain_user_auth_data(chain_user)

    async def extend_auth_session(self, chain_user: ChainUser) -> None:
        await extend_auth_session_silently(chain_user.chain, chain_user.user_id)

    async def find_class_by_id(
        self, class_id: str
    ) -> Union[RezervoClass, BookingError, AuthenticationError]:
        ibooking_token = await fetch_public_ibooking_token()
        if isinstance(ibooking_token, AuthenticationError):
            log.error("Failed to retrieve public ibooking token")
            return ibooking_token
        log.debug(f"Searching for class by id: {class_id}")
        # TODO: handle different domains
        async with HttpClient.singleton().get(
            f"{CLASS_URL}?token={ibooking_token}&id={class_id}&lang=no"
        ) as class_response:
            if not class_response.ok:
                log.error("Class get request failed")
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
        auth_data: IBookingAuthData,
        class_id: str,
    ) -> BookingResult | BookingError:
        try:
            ibooking_class_id = int(class_id)
        except ValueError:
            log.error(f"Invalid ibooking class id: {class_id}")
            return BookingError.MALFORMED_CLASS
        return await book_ibooking_class(
            self.ibooking_domain, auth_data.ibooking_token.token, ibooking_class_id
        )

    async def _cancel_booking(
        self,
        auth_data: IBookingAuthData,
        _class: RezervoClass,
    ) -> bool:
        try:
            ibooking_class_id = int(_class.id)
        except ValueError:
            log.error(f"Invalid ibooking class id: {_class.id}")
            return False
        return await cancel_booking(
            self.ibooking_domain, auth_data.ibooking_token.token, ibooking_class_id
        )

    async def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: Optional[list[LocationIdentifier]] = None,
    ) -> Optional[list[UserSession]]:
        auth_res = await self._authenticate(chain_user)
        if isinstance(auth_res, AuthenticationError):
            log.error(
                f"Authentication failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return None
        async with create_client_session() as session:
            async with session.get(
                MY_SESSIONS_URL, headers={"x-b2c-token": auth_res.access_token.token}
            ) as res:
                sessions_json = await res.json()
        datetime_now = datetime.now().astimezone()
        past_and_booked_sessions = []
        for session_json in sessions_json["bookings"]:
            if session_json["type"] != "groupclass":
                continue
            ibooking_session = pydantic.parse_obj_as(SitSession, session_json)
            session = UserSession(
                chain=chain_user.chain,
                class_id=str(ibooking_session.class_field.id),
                user_id=chain_user.user_id,
                status=session_state_from_ibooking(ibooking_session.status),
                position_in_wait_list=ibooking_session.class_field.wait_list.user_position,
                class_data=SessionRezervoClass(
                    **self.rezervo_class_from_ibooking_class(
                        ibooking_class_from_sit_session_class(
                            ibooking_session.class_field
                        )
                    ).dict()
                ),
            )
            if datetime_now < session.class_data.start_time or session.status in [
                SessionState.CONFIRMED,
                SessionState.NOSHOW,
            ]:
                past_and_booked_sessions.append(session)
        return past_and_booked_sessions

    async def fetch_schedule(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        return await self.fetch_ibooking_schedule(
            self.ibooking_domain,
            await fetch_public_ibooking_token(),
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
            id=str(ibooking_class.id),
            start_time=tz_aware_iso_from_ibooking_date_str(ibooking_class.from_field),  # type: ignore
            end_time=tz_aware_iso_from_ibooking_date_str(ibooking_class.to),  # type: ignore
            location=RezervoLocation(
                id=self.location_from_provider_location_identifier(  # type: ignore
                    ibooking_class.studio.id
                ),
                studio=ibooking_class.studio.name,
                room=ibooking_class.room,
            ),
            is_bookable=ibooking_class.bookable,
            is_cancelled=ibooking_class.cancel_text is not None,
            cancel_text=ibooking_class.cancel_text,
            total_slots=ibooking_class.capacity,
            available_slots=ibooking_class.available,
            waiting_list_count=ibooking_class.waitlist.count,
            activity=RezervoActivity(
                id=str(ibooking_class.activity_id),
                name=standardize_activity_name(ibooking_class.name),
                category=determine_activity_category(ibooking_class.category.name).name,
                description=ibooking_class.description,
                color=ibooking_class.color,
                image=ibooking_class.image,
            ),
            instructors=[
                RezervoInstructor(name=s.name) for s in ibooking_class.instructors
            ],
            user_status=ibooking_class.user_status,
            booking_opens_at=tz_aware_iso_from_ibooking_date_str(  # type: ignore
                ibooking_class.booking_opens_at
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
        async with HttpClient.singleton().get(
            f"{CLASSES_SCHEDULE_URL}"
            f"?token={token}"
            f"{f'&from={from_iso}' if from_iso is not None else ''}"
            f"{('&studios=' + ','.join([str(s) for s in studios])) if studios else ''}"
            f"&lang=no"
        ) as res:
            if not res.ok:
                return None
            json_res = await res.json()
        return RezervoSchedule(
            days=[
                RezervoDay(
                    date=day.date,
                    day_name=day.day_name,
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
        ibooking_token = await fetch_public_ibooking_token()
        if isinstance(ibooking_token, AuthenticationError):
            log.error("Failed to retrieve public ibooking token")
            return ibooking_token
        schedule = await self.fetch_ibooking_schedule(
            domain,
            ibooking_token,
            14,
            studios=(
                [studio]
                if (
                    studio := self.provider_location_identifier_from_location_identifier(
                        _class_config.location_id
                    )
                )
                is not None
                else None
            ),
        )
        if schedule is None:
            log.error("Schedule get request denied")
            return BookingError.ERROR
        _class = find_class_in_schedule_by_config(_class_config, schedule)
        if isinstance(_class, BookingError):
            log.warning(f"Could not find class matching criteria: {_class_config}")
        return _class

    async def verify_authentication(self, credentials: ChainUserCredentials) -> bool:
        return credentials.password is not None and await verify_sit_credentials(
            credentials.username, credentials.password
        )

    async def initiate_totp_flow(
        self, chain_identifier: ChainIdentifier, user_id: UUID
    ) -> None:
        return await initiate_auth_session_interactively(chain_identifier, user_id)
