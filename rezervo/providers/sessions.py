from datetime import datetime, timezone

from rezervo.consts import WEEKDAYS
from rezervo.schemas.config.user import ChainConfig
from rezervo.schemas.schedule import RezervoClass, RezervoSchedule


def get_user_planned_sessions_from_schedule(
    chain_config: ChainConfig, schedule: RezervoSchedule
) -> list[RezervoClass]:
    if not chain_config.active:
        return []
    classes: list[RezervoClass] = []
    for d in schedule.days:
        for c in d.classes:
            for cc in chain_config.recurring_bookings:
                if d.day_name != WEEKDAYS[cc.weekday]:
                    continue
                if c.activity.id != str(cc.activity_id):
                    continue
                time_matches = (
                    c.start_time.hour == cc.start_time.hour
                    and c.start_time.minute == cc.start_time.minute
                )
                if not time_matches:
                    continue
                # check if booking_opens_at is in the past (if so, it is either already booked or will not be booked)
                if c.booking_opens_at < datetime.now(timezone.utc):
                    continue
                classes.append(c)
    return classes
