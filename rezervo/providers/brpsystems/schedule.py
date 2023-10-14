from datetime import datetime, timedelta
from typing import List, Union
from urllib.parse import urlencode

import requests

from rezervo.providers.brpsystems.consts import CLASSES_SCHEDULE_URL
from rezervo.providers.brpsystems.schema import (
    FscClass,
)

FSC_MAX_SCHEDULE_DAYS_PER_FETCH = 14


def fetch_fsc_schedule(
    days: int, from_date: datetime = None
) -> Union[List[FscClass], None]:
    classes: list[FscClass] = []
    if from_date is None:
        now = datetime.utcnow()
        from_date = datetime(now.year, now.month, now.day)
    days_left = days
    while days_left > 0:
        batch_size = min(FSC_MAX_SCHEDULE_DAYS_PER_FETCH, days_left)
        days_left -= batch_size
        to_date = from_date + timedelta(days=batch_size)
        query_params = {
            "period.start": from_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
            "period.end": to_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
        }
        res = requests.get(f"{CLASSES_SCHEDULE_URL}?{urlencode(query_params)}")
        if res.status_code != requests.codes.OK:
            raise Exception("Failed to fetch fsc schedule")
        classes.extend(
            [
                FscClass(**item)
                for item in res.json()
                if item.get("bookableEarliest") is not None
                and item.get("bookableLatest") is not None
            ]
        )
        from_date = to_date
    # TODO: handle unlikely duplicates (if somehow classes are included in multiple batches)
    return classes
