from abc import ABC, abstractmethod
from datetime import datetime

from rezervo import models
from rezervo.consts import WEEKDAYS
from rezervo.errors import AuthenticationError, BookingError
from rezervo.http_client import HttpClient
from rezervo.providers.mirage.schema_generated import (
    BookingResult as MirageBookingResult,
)
from rezervo.providers.mirage.schema_generated import (
    LoginResponse,
    RezervoMirageClass,
    ScheduleResponse,
)
from rezervo.providers.mirage.schema_generated import (
    Session as MirageSession,
)
from rezervo.providers.provider import Provider
from rezervo.providers.schedule import find_class_in_schedule_by_config
from rezervo.providers.schema import LocationIdentifier
from rezervo.schemas.config.config import read_app_config
from rezervo.schemas.config.user import (
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

type MirageAuthData = str
type MirageLocationIdentifier = str

FIND_CLASS_SEARCH_DAYS = 8


class MirageProvider(Provider[MirageAuthData, MirageLocationIdentifier], ABC):
    @property
    @abstractmethod
    def mirage_chain_identifier(self) -> str:
        raise NotImplementedError()

    def _chain_url(self, *segments: str) -> str:
        base = read_app_config().mirage.base_url.rstrip("/")
        return "/".join(
            [base, "api", "chains", self.mirage_chain_identifier, *segments]
        )

    @staticmethod
    def _auth_headers(auth_data: MirageAuthData) -> dict[str, str]:
        return {"Authorization": f"Bearer {auth_data}"}

    async def _login(
        self, username: str, password: str | None
    ) -> MirageAuthData | AuthenticationError:
        if password is None:
            return AuthenticationError.INVALID_CREDENTIALS
        async with HttpClient.singleton().post(
            self._chain_url("auth", "login"),
            json={"username": username, "password": password},
        ) as res:
            if res.status == 401:
                return AuthenticationError.INVALID_CREDENTIALS
            if not res.ok:
                log.error(f"Mirage login failed ({res.status}): {await res.text()}")
                return AuthenticationError.ERROR
            return LoginResponse(**await res.json()).accessToken

    async def _authenticate(
        self, chain_user: ChainUser
    ) -> MirageAuthData | AuthenticationError:
        auth_data = await self._login(chain_user.username, chain_user.password)
        if isinstance(auth_data, AuthenticationError):
            log.error(
                f"Failed to authenticate '{chain_user.chain}' user '{chain_user.username}'"
            )
        return auth_data

    async def verify_authentication(self, credentials: ChainUserCredentials) -> bool:
        return not isinstance(
            await self._login(credentials.username, credentials.password),
            AuthenticationError,
        )

    def _rezervo_class_from_mirage_class(self, m: RezervoMirageClass) -> RezervoClass:
        category = determine_activity_category(m.activity.name)
        now = datetime.now().astimezone()
        return RezervoClass(
            id=m.id,
            start_time=m.startTime,
            end_time=m.endTime,
            location=RezervoLocation(
                id=m.location.identifier,
                studio=m.location.studio,
                room=m.location.room,
            ),
            activity=RezervoActivity(
                id=m.activity.id,
                name=standardize_activity_name(m.activity.name),
                category=category.name,
                description=m.activity.description,
                additional_information=m.activity.additionalInformation,
                color=category.color,
                image=m.activity.image,
            ),
            instructors=[RezervoInstructor(name=i.name) for i in m.instructors],
            is_bookable=m.bookingOpensAt <= now < m.startTime,
            is_cancelled=m.isCancelled,
            cancel_text=m.cancelText,
            total_slots=m.totalSlots,
            available_slots=m.availableSlots,
            waiting_list_count=m.waitingListCount,
            user_status=None,
            booking_opens_at=m.bookingOpensAt,
        )

    async def fetch_schedule(
        self,
        from_date: datetime,
        days: int,
        locations: list[LocationIdentifier],
    ) -> RezervoSchedule:
        async with HttpClient.singleton().get(
            self._chain_url("schedule"),
            params={
                "from": from_date.date().isoformat(),
                "days": days,
                "locations": ",".join(locations),
            },
        ) as res:
            if not res.ok:
                raise RuntimeError(
                    f"Mirage schedule request failed ({res.status}): {await res.text()}"
                )
            schedule = ScheduleResponse(**await res.json())
        return RezervoSchedule(
            days=[
                RezervoDay(
                    # mirage returns English day names; rezervo derives its own
                    day_name=WEEKDAYS[day.date.weekday()],
                    date=day.date.isoformat(),
                    classes=[
                        self._rezervo_class_from_mirage_class(c) for c in day.classes
                    ],
                )
                for day in schedule.days
            ]
        )

    async def find_class_by_id(
        self, class_id: str
    ) -> RezervoClass | BookingError | AuthenticationError:
        async with HttpClient.singleton().get(
            self._chain_url("classes", class_id)
        ) as res:
            if res.status == 404:
                return BookingError.CLASS_MISSING
            if not res.ok:
                log.error(f"Failed to fetch mirage class '{class_id}' ({res.status})")
                return BookingError.ERROR
            return self._rezervo_class_from_mirage_class(
                RezervoMirageClass(**await res.json())
            )

    async def find_class(
        self, _class_config: Class
    ) -> RezervoClass | BookingError | AuthenticationError:
        from_date = datetime.combine(datetime.now(), datetime.min.time())
        schedule = await self.fetch_schedule(
            from_date, FIND_CLASS_SEARCH_DAYS, [_class_config.location_id]
        )
        return find_class_in_schedule_by_config(_class_config, schedule)

    async def _book_class(
        self,
        auth_data: MirageAuthData,
        class_id: str,
    ) -> BookingResult | BookingError:
        async with HttpClient.singleton().post(
            self._chain_url("bookings"),
            json={"classId": class_id},
            headers=self._auth_headers(auth_data),
        ) as res:
            if not res.ok:
                log.error(f"Mirage booking failed ({res.status}): {await res.text()}")
                return BookingError.ERROR
            result = MirageBookingResult(**await res.json())
        return BookingResult(
            status=models.SessionState(result.status.value),
            position_in_wait_list=result.positionInWaitList,
        )

    async def _cancel_booking(
        self,
        auth_data: MirageAuthData,
        _class: RezervoClass,
    ) -> bool:
        async with HttpClient.singleton().delete(
            self._chain_url("bookings", _class.id),
            headers=self._auth_headers(auth_data),
        ) as res:
            if not res.ok:
                log.error(
                    f"Mirage cancellation failed for class '{_class.id}' ({res.status})"
                )
            return res.ok

    async def _fetch_past_and_booked_sessions(
        self,
        chain_user: ChainUser,
        locations: list[LocationIdentifier] | None = None,
    ) -> list[UserSession] | None:
        auth_data = await self._authenticate(chain_user)
        if isinstance(auth_data, AuthenticationError):
            return None
        async with HttpClient.singleton().get(
            self._chain_url("sessions"),
            headers=self._auth_headers(auth_data),
        ) as res:
            if not res.ok:
                log.error(
                    f"Failed to retrieve mirage sessions for '{chain_user.username}' ({res.status})"
                )
                return None
            sessions = [MirageSession(**s) for s in await res.json()]
        return [
            UserSession(
                chain=chain_user.chain,
                class_id=s.class_.id,
                user_id=chain_user.user_id,
                status=models.SessionState(s.status.value),
                position_in_wait_list=s.positionInWaitList,
                class_data=SessionRezervoClass(
                    **self._rezervo_class_from_mirage_class(s.class_).model_dump()
                ),
            )
            for s in sessions
            if locations is None or s.class_.location.identifier in locations
        ]
