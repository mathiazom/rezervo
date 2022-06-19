from typing import Dict, Any, Optional

import requests
from requests import RequestException

from auth import AuthenticationError
from config import Config
from consts import WEEKDAYS
from errors import BookingError


def notify_slack(slack_token: str, channel: str, message: str):
    res = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={'Authorization': f'Bearer {slack_token}'},
        json={
            "channel": channel,
            "text": message
        }
    )
    if not (res.ok and res.json()['ok']):
        print(f"[FAILED] Could not post notification to Slack: {res.text}")
        return False
    return True


def notify_auth_failure(notifications_config: Config, error: AuthenticationError = None,
                        check_run: bool = False) -> None:
    if 'slack' in notifications_config:
        slack_config = notifications_config.slack
        return notify_auth_failure_slack(slack_config.bot_token, slack_config.channel_id, slack_config.user_id, error,
                                         check_run)
    print("[WARNING] No notification targets, auth failure notification will not be sent!")


AUTH_FAILURE_REASONS_SLACK = {
    AuthenticationError.INVALID_CREDENTIALS: "Ugyldig brukernavn eller passord :key:",
    AuthenticationError.AUTH_TEMPORARILY_BLOCKED: "Midlertidig utestengt :no_entry:",
    AuthenticationError.TOKEN_EXTRACTION_FAILED: "Klarte ikke å hente autentiseringsnøkkel :sleuth_or_spy:",
    AuthenticationError.TOKEN_VALIDATION_FAILED: "Klarte ikke å verifisere autentiseringsnøkkel :interrobang:"
}


def notify_auth_failure_slack(slack_token: str, channel: str, user: str, error: AuthenticationError = None,
                              check_run: bool = False) -> None:
    message = f"{':warning: Forhåndssjekk feilet!' if check_run else ':dizzy_face:'} Klarte ikke å logge inn som " \
              f"<@{user}>{f'. *{AUTH_FAILURE_REASONS_SLACK[error]}*' if error in AUTH_FAILURE_REASONS_SLACK else ''}"
    print(f"[INFO] Posting auth {'check ' if check_run else ''}failure notification to Slack")
    if not notify_slack(slack_token, channel, message):
        print(f"[FAILED] Could not post auth {'check ' if check_run else ''}failure notification to Slack")
        return
    print(f"[INFO] Auth {'check ' if check_run else ''}failure notification posted successfully to Slack.")
    return


def notify_booking_failure(notifications_config: Config, _class_config: Dict[str, Any], error: BookingError = None,
                           check_run: bool = False) -> None:
    if 'slack' in notifications_config:
        slack_config = notifications_config.slack
        return notify_booking_failure_slack(slack_config.bot_token, slack_config.channel_id,
                                            slack_config.user_id, _class_config, error, check_run)
    print("[WARNING] No notification targets, booking failure notification will not be sent!")


BOOKING_FAILURE_REASONS_SLACK = {
    BookingError.CLASS_MISSING: "Fant ikke timen :sleuth_or_spy:",
    BookingError.INCORRECT_START_TIME: "Feil starttid :clock7:",
    BookingError.MISSING_SCHEDULE_DAY: "Fant ikke riktig dag :calendar::mag:",
    BookingError.TOO_LONG_WAITING_TIME: "Ventetid før booking var for lang :sleeping:",
    BookingError.INVALID_CONFIG: "Ugyldig bookingkonfigurasjon :broken_heart:"
}


def notify_booking_failure_slack(slack_token: str, channel: str, user: str,
                                 _class_config: Dict[str, Any], error: BookingError = None,
                                 check_run: bool = False) -> None:
    class_name = f"{_class_config['display_name'] if 'display_name' in _class_config else _class_config['activity']}"
    class_time = f"{WEEKDAYS[_class_config['weekday']].lower()} " \
                 f"{_class_config['time']['hour']}:{_class_config['time']['minute']}"
    msg = f"{':warning: Forhåndssjekk feilet! Kan ikke booke' if check_run else ':dizzy_face: Klarte ikke å booke'} " \
          f"*{class_name}* ({class_time}) for <@{user}>" \
          f"{f'. *{BOOKING_FAILURE_REASONS_SLACK[error]}*' if error in BOOKING_FAILURE_REASONS_SLACK else ''}"
    print(f"[INFO] Posting booking failure notification to Slack")
    if not notify_slack(slack_token, channel, msg):
        print(f"[FAILED] Could not post booking failure notification to Slack")
        return
    print(f"[INFO] Booking failure notification posted successfully to Slack.")
    return


def notify_booking(notifications_config: Config, booked_class: Dict[str, Any], ical_url: str) -> None:
    if 'slack' in notifications_config:
        slack_config = notifications_config.slack
        transfersh_url = notifications_config.transfersh.url if notifications_config.transfersh else None
        return notify_booking_slack(slack_config.bot_token, slack_config.channel_id, slack_config.user_id, booked_class,
                                    ical_url, transfersh_url)
    print("[WARNING] No notification targets, booking notification will not be sent!")


def transfersh_direct_url(transfersh_url: str):
    url_parts = transfersh_url.split("/")
    return "/".join(url_parts[:3]) + "/get/" + "/".join(url_parts[3:])


def upload_ical_to_transfersh(transfersh_url: str, ical_url: str, filename: str) -> str:
    return transfersh_direct_url(
        requests.post(transfersh_url, files={filename: requests.get(ical_url).text}).text
    )


def notify_booking_slack(slack_token: str, channel: str, user: str, booked_class: Dict[str, Any], ical_url: str,
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
    if not notify_slack(slack_token, channel, message):
        print(f"[FAILED] Could not post booking notification to Slack")
        return
    print(f"[INFO] Booking notification posted successfully to Slack.")
    return
