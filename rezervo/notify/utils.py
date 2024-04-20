from typing import Optional
from urllib.parse import urlparse

from rezervo.consts import URL_QUERY_PARAM_CLASS_ID, URL_QUERY_PARAM_ISO_WEEK
from rezervo.http_client import HttpClient
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


def activity_url(
    host: Optional[str], chain_identifier: ChainIdentifier, _class: RezervoClass
):
    if host:
        return (
            f"<{host}/{chain_identifier}"
            f"?{URL_QUERY_PARAM_ISO_WEEK}={compact_iso_week_str(_class.start_time)}"
            f"&{URL_QUERY_PARAM_CLASS_ID}={_class.id}"
            f"|*{_class.activity.name}*>"
        )

    return f"*{_class.activity.name}*"
