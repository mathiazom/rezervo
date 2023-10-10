from datetime import datetime, timedelta
from typing import List, Union
from urllib.parse import urlencode

import requests

from rezervo.integrations.fsc.consts import CLASSES_SCHEDULE_URL
from rezervo.integrations.fsc.schema import (
    FscClass,
    FscWeekScheduleResponse,
)

FSC_MAX_SCHEDULE_DAYS_PER_FETCH = 14


def fetch_fsc_schedule(days: int) -> Union[List[FscClass], None]:
    classes: list[FscClass] = []
    now = datetime.utcnow()
    from_date = datetime(now.year, now.month, now.day)
    days_left = days
    while days_left > 0:
        batch_size = min(FSC_MAX_SCHEDULE_DAYS_PER_FETCH, days_left)
        days_left -= batch_size
        to_date = from_date + timedelta(days=batch_size)
        query_params = {
            "period_start": from_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
            "period_end": to_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
        }
        res = requests.get(f"{CLASSES_SCHEDULE_URL}?{urlencode(query_params)}")
        if res.status_code != requests.codes.OK:
            raise Exception("Failed to fetch fsc schedule")
        classes.extend(FscWeekScheduleResponse(**res.json()).data)
        from_date = to_date
    # TODO: handle unlikely duplicates (if somehow classes are included in multiple batches)
    return classes