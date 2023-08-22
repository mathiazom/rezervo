import datetime
import math
from typing import Union

import requests

from rezervo.consts import (
    CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH,
    CLASSES_SCHEDULE_URL,
)
from rezervo.schemas.schedule import SitDay, SitSchedule


def fetch_single_batch_sit_schedule(
    token, studio: str = None, from_iso: str = None
) -> Union[SitSchedule, None]:
    res = requests.get(
        f"{CLASSES_SCHEDULE_URL}"
        f"?token={token}"
        f"{f'&from={from_iso}' if from_iso is not None else ''}"
        f"{f'&studios={studio}' if studio is not None else ''}"
        f"&lang=no"
    )
    if res.status_code != requests.codes.OK:
        return None
    return SitSchedule(**res.json())


def fetch_sit_schedule(
    token, studio: str = None, days: int = None
) -> Union[SitSchedule, None]:
    schedule_days: list[SitDay] = []
    from_date = datetime.datetime.now().date()
    for _i in range(
        math.ceil(days / CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH)
        if days is not None
        else 1
    ):
        batch = fetch_single_batch_sit_schedule(token, studio, from_date.isoformat())
        if batch is not None:
            # api actually returns 7 days, but the extra days are empty...
            schedule_days.extend(batch.days[:CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH])
        from_date = from_date + datetime.timedelta(
            days=CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH
        )
    if days is not None:
        schedule_days = schedule_days[:days]
    return SitSchedule(days=schedule_days)
