from typing import Dict, Any

import requests


def notify_slack(slack_token: str, channel: str, user: str, booked_class: Dict[str, Any], ical_url: str):
    print(f"[INFO] Posting booking notification to Slack")
    res = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={'Authorization': f'Bearer {slack_token}'},
        json={
            "channel": channel,
            "text": f"🤖 <{ical_url}|*{booked_class['name']}* ({booked_class['from']})> er booket for <@{user}>"
        })
    if not (res.ok and res.json()['ok']):
        print(f"[FAILED] Could not post booking notification to Slack: {res.text}")
        return False
    print(f"[INFO] Booking notification posted successfully to Slack.")
    return True
