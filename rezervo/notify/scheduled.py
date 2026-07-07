import datetime

from sqlalchemy.orm import Session

from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.models import ScheduledPushNotification
from rezervo.notify.push import notify_web_push
from rezervo.utils.logging_utils import log


def send_due_scheduled_push_notifications() -> None:
    now = datetime.datetime.now()
    with SessionLocal() as db:
        due = crud.get_due_scheduled_push_notifications(db, now)
        if not due:
            log.debug("No due scheduled push notifications")
            return
        log.info(f"Processing {len(due)} due scheduled push notification(s)")
        for scheduled in due:
            _dispatch_scheduled_push_notification(db, scheduled)
            db.delete(scheduled)
            db.commit()


def _dispatch_scheduled_push_notification(
    db: Session, scheduled: ScheduledPushNotification
) -> None:
    subscriptions = crud.get_user_push_notification_subscriptions(db, scheduled.user_id)
    for subscription in subscriptions:
        if subscription.grants.reminder:
            notify_web_push(subscription, scheduled.message)
