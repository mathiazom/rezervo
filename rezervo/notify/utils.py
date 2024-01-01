from typing import Optional
from urllib.parse import urlparse

import requests

from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import RezervoClass


def upload_ical_to_transfersh(transfersh_url: str, ical_url: str, filename: str) -> str:
    return transfersh_direct_url(
        requests.post(
            transfersh_url, files={filename: requests.get(ical_url).text}
        ).text
    )


def transfersh_direct_url(url: str):
    # prepend '/get' to the url path
    u = urlparse(url.strip())
    return u._replace(path=f"/get{u.path}").geturl()


def activity_url(
    host: Optional[str], chain_identifier: ChainIdentifier, _class: RezervoClass
):
    if host:
        return (
            f"<{host}/{chain_identifier}/?classId={_class.id}|*{_class.activity.name}*>"
        )

    return f"*{_class.activity.name}*"
