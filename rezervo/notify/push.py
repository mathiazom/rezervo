import datetime
import json
import re
from typing import Optional

from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

from rezervo.consts import WEEKDAYS
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError, BookingError
from rezervo.schemas.config.config import PushNotificationSubscription
from rezervo.schemas.config.user import Class
from rezervo.schemas.schedule import RezervoClass
from rezervo.settings import get_settings
from rezervo.utils.logging_utils import log

AUTH_FAILURE_REASONS = {
    AuthenticationError.INVALID_CREDENTIALS: "Ugyldig brukernavn eller passord 🔐",
    AuthenticationError.AUTH_TEMPORARILY_BLOCKED: "Midlertidig utestengt ⛔",
    AuthenticationError.TOKEN_EXTRACTION_FAILED: "Klarte ikke å hente autentiseringsnøkkel 🕵️",
    AuthenticationError.TOKEN_VALIDATION_FAILED: "Klarte ikke å verifisere autentiseringsnøkkel ‽",
}

BOOKING_FAILURE_REASONS = {
    BookingError.CLASS_MISSING: "Fant ikke timen 🕵",
    BookingError.INCORRECT_START_TIME: "Feil starttid 🕖",
    BookingError.MISSING_SCHEDULE_DAY: "Fant ikke riktig dag 📅🔍",
    BookingError.TOO_LONG_WAITING_TIME: "Ventetid før booking var for lang 💤",
    BookingError.INVALID_CONFIG: "Ugyldig bookingkonfigurasjon 💔",
}


def notify_web_push(subscription: PushNotificationSubscription, message: str) -> bool:
    settings = get_settings()
    try:
        res = webpush(
            subscription_info=subscription.dict(),
            data=json.dumps({"title": "rezervo", "message": message}),
            vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{settings.WEB_PUSH_EMAIL}"},
        )
    except WebPushException as e:
        log.error(
            f"Web push notification failed for endpoint {subscription.endpoint}: {e}"
        )
        if re.search(r"(410 Gone)|(404 Not Found)", e.message) is not None:
            log.warning(
                "Removing expired or invalid web push subscription from database"
            )
            with SessionLocal() as db:
                crud.delete_push_notification_subscription(db, subscription)
        return False
    with SessionLocal() as db:
        crud.update_last_used_push_notification_subscription(db, subscription)
    return res.ok


def notify_booking_web_push(
    subscription: PushNotificationSubscription, booked_class: RezervoClass
) -> None:
    if not notify_web_push(
        subscription,
        f"{booked_class.activity.name} "
        f"({booked_class.start_time.strftime('%Y-%m-%d %H:%M')}, {booked_class.location.studio}) er booket",
    ):
        log.error("Failed to send booking notification via web push")
        return
    log.info("Booking notification posted successfully via web push")
    return


def notify_booking_failure_web_push(
    subscription: PushNotificationSubscription,
    _class_config: Optional[Class] = None,
    error: Optional[BookingError] = None,
    check_run: bool = False,
) -> None:
    if _class_config is None:
        msg = (
            f"{'⚠️ Forhåndssjekk feilet!' if check_run else '😵'} Klarte ikke å booke time"
            f". {BOOKING_FAILURE_REASONS[error]}"
            if error in BOOKING_FAILURE_REASONS
            else ""
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
            f"{'⚠️ Forhåndssjekk feilet! Kan ikke booke' if check_run else '😵 Klarte ikke å booke'} "
            f"{class_name} ({class_time})"
            f"{f'. {BOOKING_FAILURE_REASONS[error]}' if error in BOOKING_FAILURE_REASONS else ''}"
        )
    log.debug(
        f"Posting booking {'check ' if check_run else ''}failure notification via web push"
    )
    if not notify_web_push(subscription, msg):
        log.error("Failed to send booking failure notification via web push")
        return
    log.info("Booking failure notification posted successfully via web push")
    return


def notify_auth_failure_web_push(
    subscription: PushNotificationSubscription,
    error: Optional[AuthenticationError] = None,
    check_run: bool = False,
) -> None:
    msg = (
        f"{'⚠️ Forhåndssjekk feilet!' if check_run else '😵'} Klarte ikke å logge inn"
        f". {AUTH_FAILURE_REASONS[error]}"
        if error in AUTH_FAILURE_REASONS
        else ""
    )
    log.debug(
        f"Posting auth {'check ' if check_run else ''}failure notification via web push"
    )
    if not notify_web_push(subscription, msg):
        log.error("Failed to send auth failure notification via web push")
        return
    log.info(
        f"Auth {'check ' if check_run else ''}failure notification posted successfully via web push"
    )
    return


def notify_friend_request_web_push(
    subscription: PushNotificationSubscription, sender_name: str
) -> None:
    if not notify_web_push(
        subscription, f"{sender_name} har sendt deg en venneforespørsel"
    ):
        log.error("Failed to send friend request notification via web push")
        return
    log.info("Friend request notification posted successfully via web push")
    return
