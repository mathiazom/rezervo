import datetime
import time
from typing import Any, Dict, List, Optional

from requests import RequestException
from slack_sdk import WebClient as SlackClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from starlette.datastructures import Headers

from rezervo.consts import (
    SLACK_ACTION_ADD_BOOKING_TO_CALENDAR,
    SLACK_ACTION_CANCEL_BOOKING,
    WEEKDAYS,
)
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.models import SlackClassNotificationReceipt
from rezervo.schemas.config.user import ChainIdentifier, Class
from rezervo.schemas.schedule import RezervoClass
from rezervo.schemas.slack import CancelBookingActionValue
from rezervo.utils.logging_utils import err, warn

from .utils import activity_url, upload_ical_to_transfersh


def notify_slack(
    slack_token: str,
    channel: str,
    message: str,
    message_blocks: Optional[List[Dict[str, Any]]] = None,
    thread_ts: Optional[str] = None,
) -> Optional[str]:
    try:
        response = SlackClient(token=slack_token).chat_postMessage(
            channel=channel,
            text=message,
            blocks=message_blocks,
            thread_ts=thread_ts,
            unfurl_links=False,
            unfurl_media=False,
        )
        return response.get("ts")
    except SlackApiError as e:
        err.log(f"Could not post notification to Slack: {e.response['error']}")
        return None


def delete_scheduled_message_slack(
    slack_token: str, channel_id: str, scheduled_message_id: str
) -> bool:
    try:
        res = SlackClient(token=slack_token).chat_deleteScheduledMessage(
            channel=channel_id,
            scheduled_message_id=scheduled_message_id,
        )
        if not res.get("ok", False):
            err.log(
                f"Could not delete scheduled message from Slack: {res.get('error')}"
            )
            return False
        print(f"Deleted scheduled message ({scheduled_message_id}) from Slack")
    except SlackApiError as e:
        err.log(f"Could not delete scheduled message from Slack: {e.response['error']}")
        return False
    return True


def find_user_dm_channel_id(slack_token: str, user_id: str) -> Optional[str]:
    try:
        res = SlackClient(token=slack_token).conversations_open(users=user_id)
        if res is None or not res.get("ok", False):
            err.log(
                f"Could not find user direct message channel id on Slack"
                f"{(': ' + str(res.get('error'))) if res is not None else ''}"
            )
            return None
        channel_id = res.get("channel").get("id")  # type: ignore
        print(f"Located channel id of user direct message: {channel_id}")
        return channel_id
    except SlackApiError as e:
        err.log(
            f"Could not find user direct message channel id on Slack: {e.response['error']}"
        )
        return None


def schedule_dm_slack(
    slack_token: str,
    user_id: str,
    post_at: int,
    message: str,
    message_blocks: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    try:
        res = SlackClient(token=slack_token).chat_scheduleMessage(
            channel=user_id,
            text=message,
            blocks=message_blocks,
            post_at=post_at,
            unfurl_links=False,
            unfurl_media=False,
        )
        print(f"Scheduled direct message to Slack: {res['message']['text']}")
        return res.data["scheduled_message_id"]  # type: ignore
    except SlackApiError as e:
        err.log(f"Could not schedule direct message to Slack: {e.response['error']}")
        return None


def delete_scheduled_dm_slack(slack_token: str, user_id: str, reminder_id: str):
    channel_id = find_user_dm_channel_id(slack_token, user_id)
    if channel_id is None:
        err.log(
            "Could not find correct channel to delete scheduled direct message from Slack"
        )
        return
    delete_scheduled_message_slack(slack_token, channel_id, reminder_id)


def schedule_class_reminder_slack(
    slack_token: str,
    user_id: str,
    host: Optional[str],
    chain_identifier: ChainIdentifier,
    _class: RezervoClass,
    hours_before: float,
) -> Optional[str]:
    reminder_time = _class.start_time - datetime.timedelta(hours=hours_before)
    reminder_timestamp = int(time.mktime(reminder_time.timetuple()))
    message = (
        f"Husk *{activity_url(host, chain_identifier, _class)}* "
        f"({_class.start_time.isoformat(timespec='minutes')}, *{_class.location.studio}*) "
        f"om {hours_before:g} time{'r' if hours_before > 1 else ''}!"
    )
    return schedule_dm_slack(slack_token, user_id, reminder_timestamp, message)


AUTH_FAILURE_REASONS = {
    AuthenticationError.INVALID_CREDENTIALS: "Ugyldig brukernavn eller passord :key:",
    AuthenticationError.AUTH_TEMPORARILY_BLOCKED: "Midlertidig utestengt :no_entry:",
    AuthenticationError.TOKEN_EXTRACTION_FAILED: "Klarte ikke å hente autentiseringsnøkkel :sleuth_or_spy:",
    AuthenticationError.TOKEN_VALIDATION_FAILED: "Klarte ikke å verifisere autentiseringsnøkkel :interrobang:",
}


def notify_auth_failure_slack(
    slack_token: str,
    channel: str,
    user_id: str,
    error: Optional[AuthenticationError] = None,
    thread_ts: Optional[str] = None,
    check_run: bool = False,
) -> None:
    message = (
        f"{':warning: Forhåndssjekk feilet!' if check_run else ':dizzy_face:'} Klarte ikke å logge inn som "
        f"<@{user_id}>{f'. *{AUTH_FAILURE_REASONS[error]}*' if error in AUTH_FAILURE_REASONS else ''}"
    )
    print(f"Posting auth {'check ' if check_run else ''}failure notification to Slack")
    if notify_slack(slack_token, channel, message, thread_ts=thread_ts) is None:
        err.log(
            f"Could not post auth {'check ' if check_run else ''}failure notification to Slack"
        )
        return
    print(
        f"Auth {'check ' if check_run else ''}failure notification posted successfully to Slack."
    )
    return


BOOKING_FAILURE_REASONS = {
    BookingError.CLASS_MISSING: "Fant ikke timen :sleuth_or_spy:",
    BookingError.INCORRECT_START_TIME: "Feil starttid :clock7:",
    BookingError.MISSING_SCHEDULE_DAY: "Fant ikke riktig dag :calendar::mag:",
    BookingError.TOO_LONG_WAITING_TIME: "Ventetid før booking var for lang :sleeping:",
    BookingError.INVALID_CONFIG: "Ugyldig bookingkonfigurasjon :broken_heart:",
}


def notify_booking_failure_slack(
    slack_token: str,
    channel: str,
    user_id: str,
    _class_config: Optional[Class] = None,
    error: Optional[BookingError] = None,
    check_run: bool = False,
) -> None:
    if _class_config is None:
        msg = (
            f"{':warning: Forhåndssjekk feilet ' if check_run else ':dizzy_face: Klarte ikke å booke'} "
            f"for <@{user_id}>{f'. *{BOOKING_FAILURE_REASONS[error]}*' if error in BOOKING_FAILURE_REASONS else ''}"
        )
    else:
        class_name = str(
            _class_config.display_name
            if _class_config.display_name is not None
            else _class_config.activity_id
        )
        class_time = (
            f"{WEEKDAYS[_class_config.weekday].lower()} "
            f"{datetime.time(_class_config.start_time.hour, _class_config.start_time.minute).strftime('%H:%M')}"
        )
        msg = (
            f"{':warning: Forhåndssjekk feilet! Kan ikke booke' if check_run else ':dizzy_face: Klarte ikke å booke'} "
            f"*{class_name}* ({class_time}) for <@{user_id}>"
            f"{f'. *{BOOKING_FAILURE_REASONS[error]}*' if error in BOOKING_FAILURE_REASONS else ''}"
        )
    print("Posting booking failure notification to Slack")
    if notify_slack(slack_token, channel, msg) is None:
        err.log("Could not post booking failure notification to Slack")
        return
    print("Booking failure notification posted successfully to Slack.")
    return


WORKING_EMOJI_NAME = "rezervo-working"


def notify_working_slack(slack_token: str, channel: str, message_ts: str):
    try:
        SlackClient(token=slack_token).reactions_add(
            channel=channel, timestamp=message_ts, name=WORKING_EMOJI_NAME
        )
        print("'Working' reaction posted successfully to Slack.")
    except SlackApiError as e:
        err.log(f"Could not post 'working' reaction to Slack: {e.response['error']}")


def notify_not_working_slack(slack_token: str, channel: str, message_ts: str):
    try:
        SlackClient(token=slack_token).reactions_remove(
            channel=channel, timestamp=message_ts, name=WORKING_EMOJI_NAME
        )
        print("'Working' reaction removed successfully from Slack message.")
    except SlackApiError as e:
        if e.response["error"] == "no_reaction":
            # reaction not present, assume success
            return
        err.log(
            f"Could not remove 'working' reaction from Slack message: {e.response['error']}"
        )


def notify_cancellation_slack(slack_token: str, channel: str, source_ts: str) -> bool:
    try:
        # Retrieve original message
        conversation = SlackClient(token=slack_token).conversations_history(
            channel=channel, latest=source_ts, limit=1, inclusive=True
        )
        message: dict = conversation.data["messages"][0]  # type: ignore
        cancelled_text_prefix = "[AVBESTILT!]"
        # If already cancelled, abort with success
        if message["text"].startswith(cancelled_text_prefix):
            return True
        # Remove booking emoji and strike out original text
        new_message = f'~{message["blocks"][0]["text"]["text"]}~'.replace(
            BOOKING_EMOJI, CANCELLATION_EMOJI, 1
        )
        message["blocks"][0]["text"]["text"] = new_message
        # Remove all message actions
        message["blocks"] = [b for b in message["blocks"] if b["type"] != "actions"]
        # Update original message to reflect cancellation
        SlackClient(token=slack_token).chat_update(
            channel=channel,
            ts=source_ts,
            text=f'{cancelled_text_prefix} {message["text"]}',  # fallback text if 'blocks' don't work
            blocks=message["blocks"],
        )
        notify_not_working_slack(slack_token, channel, source_ts)
        # Notify in thread
        notify_slack(
            slack_token,
            channel,
            ":broken_heart: Timen er avbestilt",
            thread_ts=source_ts,
        )
    except SlackApiError as e:
        err.log(
            f"Could not post cancellation notification to Slack: {e.response['error']}"
        )
        return False
    return True


CANCELLATION_FAILURE_REASONS = {
    BookingError.CLASS_MISSING: "Klarte ikke å hente timen :sleuth_or_spy:",
    BookingError.CANCELLING_WITHOUT_BOOKING: "Timen var ikke booket :interrobang:",
}


def notify_cancellation_failure_slack(
    slack_token: str,
    channel: str,
    source_ts: str,
    error: BookingError | AuthenticationError,
) -> None:
    try:
        notify_not_working_slack(slack_token, channel, source_ts)
        # Notify failure in thread
        cancellation_failure_text = (
            f". {CANCELLATION_FAILURE_REASONS[error]}"
            if isinstance(error, BookingError) and error in CANCELLATION_FAILURE_REASONS
            else ""
        )
        auth_failure_text = (
            f". {AUTH_FAILURE_REASONS[error]}"
            if isinstance(error, AuthenticationError) and error in AUTH_FAILURE_REASONS
            else ""
        )
        message = (
            f":dizzy_face: Avbestilling feilet"
            f"{cancellation_failure_text}"
            f"{auth_failure_text}"
        )
        notify_slack(slack_token, channel, message, thread_ts=source_ts)
    except SlackApiError as e:
        err.log(
            f"Could not post cancellation failure notification to Slack: {e.response['error']}"
        )
        return
    print("Cancellation failure notification posted successfully to Slack.")


def show_unauthorized_action_modal_slack(slack_token: str, trigger_id: str):
    try:
        SlackClient(token=slack_token).views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "rezervo"},
                "close": {"type": "plain_text", "text": ":cry: Lukk", "emoji": True},
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": ":four::zero::three:",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": "Det er lov å prøve seg :peach:"}
                        ],
                    },
                ],
            },
        )
    except SlackApiError as e:
        err.log(
            f"Could not display unauthorized action modal in Slack: {e.response['error']}"
        )
        return
    print("Unauthorized action modal displayed successfully in Slack.")


def notify_booking_slack(
    slack_token: str,
    channel: str,
    user_id: str,
    host: Optional[str],
    chain_identifier: ChainIdentifier,
    booked_class: RezervoClass,
    ical_url: Optional[str] = None,
    transfersh_url: Optional[str] = None,
    scheduled_reminder_id: Optional[str] = None,
) -> None:
    message_blocks = build_booking_message_blocks(
        chain_identifier, booked_class, user_id, host, None, scheduled_reminder_id
    )
    if transfersh_url:
        filename = f"{booked_class.id}.ics"
        print(f"Uploading {filename} to {transfersh_url}")
        try:
            ical_tsh_url = (
                upload_ical_to_transfersh(transfersh_url, ical_url, filename)
                if ical_url is not None
                else None
            )
            message_blocks = build_booking_message_blocks(
                chain_identifier,
                booked_class,
                user_id,
                host,
                ical_tsh_url,
                scheduled_reminder_id,
            )
        except RequestException:
            warn.log(
                "Could not upload ical event to transfer.sh instance, skipping ical link in notification."
            )
    print("Posting booking notification to Slack")
    slack_notification_ts = notify_slack(
        slack_token, channel, message_blocks["message"], message_blocks["blocks"]
    )
    if slack_notification_ts is None:
        err.log("Could not post booking notification to Slack")
        return
    print("Booking notification posted successfully to Slack.")
    with SessionLocal() as db:
        db.add(
            SlackClassNotificationReceipt(
                slack_user_id=user_id,
                chain=chain_identifier,
                class_id=booked_class.id,
                channel_id=channel,
                message_id=slack_notification_ts,
                scheduled_reminder_id=scheduled_reminder_id,
                expires_at=booked_class.start_time,
            )
        )
        db.commit()
    return


BOOKING_EMOJI = ":robot_face:"
CANCELLATION_EMOJI = ":no_entry:"


def build_booking_message_blocks(
    chain_identifier: ChainIdentifier,
    booked_class: RezervoClass,
    user_id: str,
    host: Optional[str],
    ical_tsh_url: Optional[str] = None,
    scheduled_reminder_id: Optional[str] = None,
):
    buttons = [
        {
            "type": "button",
            "action_id": SLACK_ACTION_CANCEL_BOOKING,
            "value": (
                CancelBookingActionValue(
                    chain_identifier=chain_identifier,
                    user_id=user_id,
                    class_id=booked_class.id,
                    scheduled_reminder_id=scheduled_reminder_id,
                ).json()
            ),
            "text": {"type": "plain_text", "text": ":no_entry: Avbestill"},
            "confirm": {
                "title": {"type": "plain_text", "text": "Er du sikker?"},
                "text": {
                    "type": "plain_text",
                    "text": f"Du er i ferd med å avbestille "
                    f"{booked_class.activity.name} ({booked_class.start_time.isoformat(timespec='minutes')}, "
                    f"*{booked_class.location.studio}*). "
                    f"Dette kan ikke angres!",
                },
                "confirm": {"type": "plain_text", "text": "Avbestill"},
                "deny": {"type": "plain_text", "text": "Avbryt"},
                "style": "danger",
            },
        }
    ]
    if ical_tsh_url:
        buttons.insert(
            0,
            {
                "type": "button",
                "action_id": SLACK_ACTION_ADD_BOOKING_TO_CALENDAR,
                "text": {"type": "plain_text", "text": ":calendar: Legg i kalender"},
                "url": ical_tsh_url,
            },
        )
    message = (
        f"{BOOKING_EMOJI} {activity_url(host, chain_identifier, booked_class)} "
        f"({booked_class.start_time.isoformat(timespec='minutes')}, "
        f"*{booked_class.location.studio}*) er booket for <@{user_id}>"
    )
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": message}}
    ]
    if len(buttons) > 0:
        blocks.append({"type": "actions", "elements": buttons})
    return {"message": message, "blocks": blocks}


def verify_slack_request(body: bytes, headers: Headers, signing_secret: str) -> bool:
    # see https://api.slack.com/authentication/verifying-requests-from-slack
    timestamp = headers.get("x-slack-request-timestamp")
    signature = headers.get("x-slack-signature")
    if timestamp is None or signature is None:
        return False
    return SignatureVerifier(signing_secret=signing_secret).is_valid(
        body, timestamp, signature
    )
