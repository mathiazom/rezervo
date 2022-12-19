import requests


def upload_ical_to_transfersh(transfersh_url: str, ical_url: str, filename: str) -> str:
    return transfersh_direct_url(
        requests.post(transfersh_url, files={filename: requests.get(ical_url).text}).text
    )


def transfersh_direct_url(transfersh_url: str):
    url_parts = transfersh_url.split("/")
    return "/".join(url_parts[:3]) + "/get/" + "/".join(url_parts[3:])
