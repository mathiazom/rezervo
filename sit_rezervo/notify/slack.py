import datetime
import time
from typing import Dict, Any, Optional, List

from requests import RequestException
from slack_sdk import WebClient as SlackClient
from slack_sdk.errors import SlackApiError

from ..auth import AuthenticationError
from ..consts import WEEKDAYS, SLACK_ACTION_ADD_BOOKING_TO_CALENDAR
from ..errors import BookingError
from .utils import upload_ical_to_transfersh


def notify_slack(slack_token: str, channel: str, message: str, message_blocks: Optional[List[Dict[str, Any]]] = None):
    try:
        SlackClient(token=slack_token).chat_postMessage(
            channel=channel,
            text=message,
            blocks=message_blocks
        )
    except SlackApiError as e:
        print(f"[FAILED] Could not post notification to Slack: {e.response['error']}")
        return False
    return True


def schedule_im_slack(slack_token: str, user_id: str, post_at: int, message: str,
                      message_blocks: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    try:
        res = SlackClient(token=slack_token).chat_scheduleMessage(
            channel=user_id,
            text=message,
            blocks=message_blocks,
            post_at=post_at
        )
        print(f"[INFO] Schedule notification to Slack: {res}")
        return res.data['scheduled_message_id']
    except SlackApiError as e:
        print(f"[FAILED] Could not schedule notification to Slack: {e.response['error']}")
        return None


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
                 f"{datetime.time(_class_config['time']['hour'], _class_config['time']['minute']).strftime('%H:%M')}"
    msg = f"{':warning: Forhåndssjekk feilet! Kan ikke booke' if check_run else ':dizzy_face: Klarte ikke å booke'} " \
          f"*{class_name}* ({class_time}) for <@{user}>" \
          f"{f'. *{BOOKING_FAILURE_REASONS_SLACK[error]}*' if error in BOOKING_FAILURE_REASONS_SLACK else ''}"
    print(f"[INFO] Posting booking failure notification to Slack")
    if not notify_slack(slack_token, channel, msg):
        print(f"[FAILED] Could not post booking failure notification to Slack")
        return
    print(f"[INFO] Booking failure notification posted successfully to Slack.")
    return


def notify_booking_slack(slack_token: str, channel: str, user: str, booked_class: Dict[str, Any], ical_url: str,
                         transfersh_url: Optional[str], scheduled_reminder_id: Optional[str]) -> None:
    message_blocks = booking_message_blocks(booked_class, user, scheduled_reminder_id)
    if transfersh_url:
        filename = f"{booked_class['id']}.ics"
        print(f"[INFO] Uploading {filename} to {transfersh_url}")
        try:
            ical_tsh_url = upload_ical_to_transfersh(transfersh_url, ical_url, filename)
            message_blocks = booking_message_blocks(booked_class, user, ical_tsh_url, scheduled_reminder_id)
        except RequestException:
            print(f"[WARNING] Could not upload ical event to transfer.sh instance, skipping ical link in notification.")
    print(f"[INFO] Posting booking notification to Slack")
    if not notify_slack(slack_token, channel, message_blocks['message'], message_blocks['blocks']):
        print(f"[FAILED] Could not post booking notification to Slack")
        return
    print(f"[INFO] Booking notification posted successfully to Slack.")
    return


def booking_message_blocks(booked_class: Dict[str, Any], user: str, ical_tsh_url: Optional[str] = None,
                           scheduled_reminder_id: Optional[str] = None):
    buttons = [
        # {
        #     "type": "button",
        #     "action_id": SLACK_ACTION_CANCEL_BOOKING,
        #     "value": json.dumps(
        #         {
        #             "userId": user,
        #             "classId": str(booked_class['id']),
        #             "scheduledReminderMessageId": scheduled_reminder_id
        #         }
        #     ),
        #     "text": {
        #         "type": "plain_text",
        #         "text": ":no_entry: Avbestill"
        #     },
        #     "confirm": {
        #         "title": {
        #             "type": "plain_text",
        #             "text": "Er du sikker?"
        #         },
        #         "text": {
        #             "type": "plain_text",
        #             "text": f"Du er i ferd med å avbestille {booked_class['name']} ({booked_class['from']}). "
        #                     f"Dette kan ikke angres!"
        #         },
        #         "confirm": {
        #             "type": "plain_text",
        #             "text": "Avbestill"
        #         },
        #         "deny": {
        #             "type": "plain_text",
        #             "text": "Avbryt"
        #         },
        #         "style": "danger"
        #     }
        # }
    ]
    if ical_tsh_url:
        buttons.insert(0, {
            "type": "button",
            "action_id": SLACK_ACTION_ADD_BOOKING_TO_CALENDAR,
            "text": {
                "type": "plain_text",
                "text": ":calendar: Legg i kalender"
            },
            "url": ical_tsh_url
        })
    message = f"🤖 *{booked_class['name']}* ({booked_class['from']}) er booket for <@{user}>"
    return {
        "message": message,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            },
            {
                "type": "actions",
                "elements": buttons
            }
        ]
    }


def schedule_class_reminder_slack(slack_token: str, user: str, _class: Dict[str, Any], hours_before: int) \
        -> Optional[str]:
    start_time = datetime.datetime.fromisoformat(_class['from'])
    reminder_time = start_time - datetime.timedelta(hours=hours_before)
    reminder_timestamp = int(time.mktime(reminder_time.timetuple()))
    message = f"Husk *{_class['name']}* ({_class['from']}) om {hours_before} timer!"
    return schedule_im_slack(slack_token, user, reminder_timestamp, message)
