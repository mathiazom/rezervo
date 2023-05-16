from typing import Dict, Any, Optional

from urllib.parse import urlparse

import requests


def upload_ical_to_transfersh(transfersh_url: str, ical_url: str, filename: str) -> str:
    return transfersh_direct_url(requests.post(transfersh_url, files={filename: requests.get(ical_url).text}).text)


def transfersh_direct_url(url: str):
    # prepend '/get' to the url path
    u = urlparse(url.strip())
    return u._replace(path=f"/get{u.path}").geturl()


def activity_url(host: Optional[str], _class: Dict[str, Any]):
    if host:
        return f"<{host}/?classId={_class['id']}|*{_class['name']}*>"

    return f"*{_class['name']}*"
