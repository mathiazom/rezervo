from typing import Dict, Any, Optional

import requests
from requests import RequestException


def transfersh_direct_url(transfersh_url: str):
    url_parts = transfersh_url.split("/")
    return "/".join(url_parts[:3]) + "/get/" + "/".join(url_parts[3:])


def upload_ical_to_transfersh(transfersh_url: str, ical_url: str, filename: str) -> str:
    return transfersh_direct_url(
        requests.post(transfersh_url, files={filename: requests.get(ical_url).text}).text
    )


def notify_slack(slack_token: str, channel: str, user: str, booked_class: Dict[str, Any], ical_url: str,
                 transfersh_url: Optional[str]) -> None:
    message = f"🤖 *{booked_class['name']}* ({booked_class['from']}) er booket for <@{user}>"
    if transfersh_url:
        filename = f"{booked_class['id']}.ics"
        print(f"[INFO] Uploading {filename} to {transfersh_url}")
        try:
            ical_tsh_url = upload_ical_to_transfersh(transfersh_url, ical_url, filename)
            message = f"🤖 <{ical_tsh_url}|*{booked_class['name']}* ({booked_class['from']})> er booket for <@{user}>"
        except RequestException:
            print(f"[WARNING] Could not upload ical event to transfer.sh instance, skipping ical link in notification.")
    print(f"[INFO] Posting booking notification to Slack")
    res = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={'Authorization': f'Bearer {slack_token}'},
        json={
            "channel": channel,
            "text": message
        }
    )
    if not (res.ok and res.json()['ok']):
        print(f"[FAILED] Could not post booking notification to Slack: {res.text}")
        return
    print(f"[INFO] Booking notification posted successfully to Slack.")
    return
