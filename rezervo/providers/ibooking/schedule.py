import datetime
import math
from typing import Optional, Union

import requests

from rezervo.providers.ibooking.consts import (
    CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH,
    CLASSES_SCHEDULE_URL,
)
from rezervo.providers.ibooking.schema import SitDay, SitSchedule


def fetch_single_batch_sit_schedule(
    token: str, studio: Optional[int] = None, from_iso: Optional[str] = None
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
    token, days: int, studio: Optional[int] = None
) -> Union[SitSchedule, None]:
    schedule_days: list[SitDay] = []
    from_date = datetime.datetime.now().date()
    for _i in range(math.ceil(days / CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH)):
        batch = fetch_single_batch_sit_schedule(token, studio, from_date.isoformat())
        if batch is not None:
            # api actually returns 7 days, but the extra days are empty...
            schedule_days.extend(batch.days[:CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH])
        from_date = from_date + datetime.timedelta(
            days=CLASSES_SCHEDULE_DAYS_IN_SINGLE_BATCH
        )
    return SitSchedule(days=schedule_days[:days])
