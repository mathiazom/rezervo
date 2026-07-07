import datetime
from urllib.parse import urlparse

import pytz

from rezervo.consts import URL_QUERY_PARAM_CLASS_ID, URL_QUERY_PARAM_ISO_WEEK
from rezervo.http_client import HttpClient
from rezervo.notify.types import AllowedTimeWindow
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import RezervoClass
from rezervo.utils.time_utils import compact_iso_week_str


async def upload_ical_to_transfersh(
    transfersh_url: str, ical_url: str, filename: str
) -> str:
    session = HttpClient.singleton()
    async with session.get(ical_url) as ical_res:
        filename = await ical_res.text()
        async with session.post(transfersh_url, files={filename: filename}) as res:
            return transfersh_direct_url(await res.text())


def transfersh_direct_url(url: str):
    # prepend '/get' to the url path
    u = urlparse(url.strip())
    return u._replace(path=f"/get{u.path}").geturl()


def window_backward_adjusted_datetime(
    dt: datetime.datetime, window: AllowedTimeWindow
) -> datetime.datetime:
    """
    Move datetime backwards until within given time window, interpreting the
    window in the local timezone it is configured in
    """

    tz = pytz.timezone("Europe/Oslo")
    local_dt = dt.astimezone(tz)
    t = local_dt.time()
    if window.not_before <= window.not_after:
        within_window = window.not_before <= t <= window.not_after
    else:  # window crosses midnight
        within_window = t >= window.not_before or t <= window.not_after
    if within_window:
        return dt
    adjusted_dt = local_dt.replace(
        tzinfo=None, hour=window.not_after.hour, minute=window.not_after.minute
    )
    if t < window.not_after:
        adjusted_dt -= datetime.timedelta(days=1)
    return tz.localize(adjusted_dt)


def compute_reminder_datetime(
    class_start_time: datetime.datetime,
    hours_before: float,
    time_window: AllowedTimeWindow | None,
) -> tuple[datetime.datetime, float]:
    reminder_datetime = class_start_time - datetime.timedelta(hours=hours_before)
    if time_window is not None:
        reminder_datetime = window_backward_adjusted_datetime(
            reminder_datetime, time_window
        )
        earliest = datetime.datetime.now(class_start_time.tzinfo) + datetime.timedelta(
            minutes=1
        )
        reminder_datetime = max(earliest, reminder_datetime)
        hours_before = (class_start_time - reminder_datetime).total_seconds() / 3600
    return reminder_datetime, hours_before


def activity_url(
    host: str | None, chain_identifier: ChainIdentifier, _class: RezervoClass
):
    if host:
        return (
            f"<{host}/{chain_identifier}"
            f"?{URL_QUERY_PARAM_ISO_WEEK}={compact_iso_week_str(_class.start_time)}"
            f"&{URL_QUERY_PARAM_CLASS_ID}={_class.id}"
            f"|*{_class.activity.name}*>"
        )

    return f"*{_class.activity.name}*"
